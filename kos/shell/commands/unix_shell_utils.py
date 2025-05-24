"""
Unix-like Shell Utilities for KOS Shell

This module provides Linux/Unix-like shell scripting and job control commands for KOS.
"""

import os
import sys
import time
import logging
import shlex
import re
import signal
import threading
import subprocess
import tempfile
from typing import Dict, List, Any, Optional, Union, Tuple

# Import KOS components
from kos.layer import klayer

# Set up logging
logger = logging.getLogger('KOS.shell.commands.unix_shell_utils')

# Background jobs registry
JOBS = {}
JOB_COUNTER = 0
JOB_LOCK = threading.Lock()

class UnixShellUtilities:
    """Unix-like shell commands for KOS shell"""
    
    @staticmethod
    def do_jobs(fs, cwd, arg):
        """
        List active jobs
        
        Usage: jobs [options]
        
        Options:
          -l      Show process IDs in addition to job number
          -p      Show process IDs only
          -r      Show running jobs only
          -s      Show stopped jobs only
        """
        args = arg.split()
        
        # Parse options
        show_pids = False
        pids_only = False
        running_only = False
        stopped_only = False
        
        for arg in args:
            if arg == '-l':
                show_pids = True
            elif arg == '-p':
                pids_only = True
            elif arg == '-r':
                running_only = True
            elif arg == '-s':
                stopped_only = True
        
        # List jobs
        results = []
        
        with JOB_LOCK:
            for job_id, job in sorted(JOBS.items()):
                if running_only and job['status'] != 'Running':
                    continue
                if stopped_only and job['status'] != 'Stopped':
                    continue
                
                if pids_only:
                    results.append(str(job['pid']))
                else:
                    status_str = '[' + job['status'] + ']'
                    if show_pids:
                        results.append(f"[{job_id}] {status_str} {job['pid']} {job['command']}")
                    else:
                        results.append(f"[{job_id}] {status_str} {job['command']}")
        
        if not results:
            return "No active jobs"
        
        return "\n".join(results)
    
    @staticmethod
    def do_bg(fs, cwd, arg):
        """
        Run jobs in the background
        
        Usage: bg [job_id...]
        
        If no job_id is specified, the current job is used.
        """
        args = arg.split()
        
        # If no job ID specified, use most recent stopped job
        if not args:
            with JOB_LOCK:
                stopped_jobs = [job_id for job_id, job in JOBS.items() if job['status'] == 'Stopped']
                if not stopped_jobs:
                    return "bg: no current job"
                job_id = max(stopped_jobs)
        else:
            # Parse job ID
            try:
                job_spec = args[0]
                if job_spec.startswith('%'):
                    job_id = int(job_spec[1:])
                else:
                    job_id = int(job_spec)
            except ValueError:
                return f"bg: {args[0]}: no such job"
        
        # Check if job exists
        with JOB_LOCK:
            if job_id not in JOBS:
                return f"bg: {job_id}: no such job"
            
            job = JOBS[job_id]
            
            # Check if job is already running
            if job['status'] == 'Running':
                return f"bg: job {job_id} already in background"
            
            # Resume job in background
            job['status'] = 'Running'
            
            # In a real implementation, we would use job control to resume the process
            # Here we simulate it
            
            return f"[{job_id}] {job['command']} &"
    
    @staticmethod
    def do_fg(fs, cwd, arg):
        """
        Bring job to the foreground
        
        Usage: fg [job_id]
        
        If no job_id is specified, the current job is used.
        """
        args = arg.split()
        
        # If no job ID specified, use most recent job
        if not args:
            with JOB_LOCK:
                if not JOBS:
                    return "fg: no current job"
                job_id = max(JOBS.keys())
        else:
            # Parse job ID
            try:
                job_spec = args[0]
                if job_spec.startswith('%'):
                    job_id = int(job_spec[1:])
                else:
                    job_id = int(job_spec)
            except ValueError:
                return f"fg: {args[0]}: no such job"
        
        # Check if job exists
        with JOB_LOCK:
            if job_id not in JOBS:
                return f"fg: {job_id}: no such job"
            
            job = JOBS[job_id]
            
            # Bring job to foreground
            status = job['status']
            job['status'] = 'Foreground'
            
            # In a real implementation, we would use job control to bring the process to the foreground
            # Here we simulate it
            
            return f"{job['command']}"
    
    @staticmethod
    def do_exec(fs, cwd, arg):
        """
        Execute a command, replacing the current process
        
        Usage: exec command [args...]
        
        This command replaces the current shell with the specified command.
        """
        if not arg:
            return "exec: no command specified"
        
        # In a real implementation, this would replace the current process
        # Here we simulate it by executing the command
        
        # Parse the command
        args = shlex.split(arg)
        command = args[0]
        
        # Try to find the command in the shell's registered commands
        from kos.shell import shell
        if command in shell.commands:
            result = shell.commands[command](fs, cwd, ' '.join(args[1:]))
            return result
        else:
            return f"exec: {command}: command not found"
    
    @staticmethod
    def do_export(fs, cwd, arg):
        """
        Set an environment variable
        
        Usage: export [NAME[=VALUE]...]
        
        If no arguments are given, print all exported variables.
        """
        if not arg:
            # Print all environment variables
            results = []
            for name, value in sorted(os.environ.items()):
                results.append(f"export {name}=\"{value}\"")
            return "\n".join(results)
        
        # Parse arguments
        args = arg.split()
        results = []
        
        for arg in args:
            if '=' in arg:
                name, value = arg.split('=', 1)
                # Remove quotes if present
                if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                
                # Set environment variable
                os.environ[name] = value
                results.append(f"export {name}=\"{value}\"")
            else:
                # Print the variable if it exists
                if arg in os.environ:
                    results.append(f"export {arg}=\"{os.environ[arg]}\"")
                else:
                    results.append(f"export: {arg}: not found")
        
        return "\n".join(results)
    
    @staticmethod
    def do_alias(fs, cwd, arg):
        """
        Define or display aliases
        
        Usage: alias [name[=value]...]
        
        If no arguments are given, print all aliases.
        """
        # Initialize aliases if not already
        if not hasattr(klayer, '_aliases'):
            klayer._aliases = {}
        
        if not arg:
            # Print all aliases
            results = []
            for name, value in sorted(klayer._aliases.items()):
                results.append(f"alias {name}='{value}'")
            
            if not results:
                return "No aliases defined"
            
            return "\n".join(results)
        
        # Parse arguments
        args = arg.split()
        results = []
        
        for arg in args:
            if '=' in arg:
                name, value = arg.split('=', 1)
                # Remove quotes if present
                if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                
                # Set alias
                klayer._aliases[name] = value
                results.append(f"alias {name}='{value}'")
            else:
                # Print the alias if it exists
                if arg in klayer._aliases:
                    results.append(f"alias {arg}='{klayer._aliases[arg]}'")
                else:
                    results.append(f"alias: {arg}: not found")
        
        return "\n".join(results)
    
    @staticmethod
    def do_unalias(fs, cwd, arg):
        """
        Remove aliases
        
        Usage: unalias name [name...]
        
        Options:
          -a      Remove all aliases
        """
        # Initialize aliases if not already
        if not hasattr(klayer, '_aliases'):
            klayer._aliases = {}
        
        if not arg:
            return "unalias: usage: unalias name [name...]"
        
        # Parse arguments
        args = arg.split()
        results = []
        
        if args[0] == '-a':
            # Remove all aliases
            klayer._aliases.clear()
            return "All aliases removed"
        
        # Remove specified aliases
        for name in args:
            if name in klayer._aliases:
                del klayer._aliases[name]
                results.append(f"Alias '{name}' removed")
            else:
                results.append(f"unalias: {name}: not found")
        
        return "\n".join(results)
    
    @staticmethod
    def do_source(fs, cwd, arg):
        """
        Execute commands from a file in the current shell
        
        Usage: source filename [arguments]
        
        This command reads and executes commands from the specified file in the current shell.
        """
        args = arg.split()
        
        if not args:
            return "source: filename argument required"
        
        filename = args[0]
        
        # Resolve path
        if not os.path.isabs(filename):
            path = os.path.join(cwd, filename)
        else:
            path = filename
        
        # Check if file exists
        if not os.path.exists(path):
            return f"source: {filename}: No such file or directory"
        
        # Read and execute commands from file
        try:
            from kos.shell import shell
            
            with open(path, 'r') as f:
                results = []
                for line in f:
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    
                    # Execute command
                    if ' ' in line:
                        cmd, cmd_args = line.split(' ', 1)
                    else:
                        cmd, cmd_args = line, ''
                    
                    if cmd in shell.commands:
                        result = shell.commands[cmd](fs, cwd, cmd_args)
                        if result:
                            results.append(result)
                    else:
                        results.append(f"source: {cmd}: command not found")
            
            return "\n".join(results)
        except Exception as e:
            return f"source: error executing {filename}: {str(e)}"
    
    @staticmethod
    def do_history(fs, cwd, arg):
        """
        Display command history
        
        Usage: history [options]
        
        Options:
          -c      Clear the history list
          -d OFFSET  Delete the history entry at OFFSET
          -w      Write the current history to the history file
          -r      Read the history file and append its contents to the history list
          NUM     Display only the last NUM lines
        """
        # Initialize history if not already
        if not hasattr(klayer, '_history'):
            klayer._history = []
        
        args = arg.split()
        
        # Parse options
        if args:
            if args[0] == '-c':
                # Clear history
                klayer._history.clear()
                return "History cleared"
            elif args[0] == '-d' and len(args) > 1:
                try:
                    offset = int(args[1])
                    if 0 <= offset < len(klayer._history):
                        del klayer._history[offset]
                        return f"Deleted history entry {offset}"
                    else:
                        return f"history: {offset}: history position out of range"
                except ValueError:
                    return f"history: {args[1]}: numeric argument required"
            elif args[0] == '-w':
                # In a real implementation, would write history to file
                return "History written"
            elif args[0] == '-r':
                # In a real implementation, would read history from file
                return "History read"
            else:
                try:
                    # Display only the last N lines
                    num = int(args[0])
                    history = klayer._history[-num:]
                except ValueError:
                    return f"history: {args[0]}: numeric argument required"
        else:
            history = klayer._history
        
        # Format history output
        results = []
        for i, cmd in enumerate(history):
            results.append(f"{i+1:5d}  {cmd}")
        
        return "\n".join(results)
    
    @staticmethod
    def do_echo(fs, cwd, arg):
        """
        Display a line of text
        
        Usage: echo [options] [string...]
        
        Options:
          -n      Do not output the trailing newline
          -e      Enable interpretation of backslash escapes
          -E      Disable interpretation of backslash escapes (default)
        """
        args = arg.split()
        
        # Parse options
        no_newline = False
        interpret_escapes = False
        
        i = 0
        while i < len(args):
            if args[i] == '-n':
                no_newline = True
                i += 1
            elif args[i] == '-e':
                interpret_escapes = True
                i += 1
            elif args[i] == '-E':
                interpret_escapes = False
                i += 1
            elif args[i].startswith('-') and args[i] != '-':
                # Process combined options
                for c in args[i][1:]:
                    if c == 'n':
                        no_newline = True
                    elif c == 'e':
                        interpret_escapes = True
                    elif c == 'E':
                        interpret_escapes = False
                i += 1
            else:
                break
        
        # Process and join remaining arguments
        output = ' '.join(args[i:])
        
        # Process escape sequences if enabled
        if interpret_escapes:
            output = output.replace('\\\\', '\\')
            output = output.replace('\\n', '\n')
            output = output.replace('\\r', '\r')
            output = output.replace('\\t', '\t')
            output = output.replace('\\v', '\v')
            output = output.replace('\\b', '\b')
            output = output.replace('\\a', '\a')
            output = output.replace('\\f', '\f')
        
        # Add newline if not suppressed
        if not no_newline:
            output += '\n'
        
        return output.rstrip('\n')  # Remove trailing newline for display
    
    @staticmethod
    def do_sleep(fs, cwd, arg):
        """
        Delay for a specified amount of time
        
        Usage: sleep NUMBER[SUFFIX]...
        
        Pause for NUMBER seconds. SUFFIX may be 's' for seconds (default),
        'm' for minutes, 'h' for hours or 'd' for days.
        """
        if not arg:
            return "sleep: missing operand\nTry 'sleep --help' for more information."
        
        args = arg.split()
        total_seconds = 0
        
        for arg in args:
            # Parse number and suffix
            match = re.match(r'^(\d+\.?\d*)([smhd])?$', arg)
            if not match:
                return f"sleep: invalid time interval '{arg}'"
            
            value, suffix = match.groups()
            try:
                value = float(value)
            except ValueError:
                return f"sleep: invalid time interval '{arg}'"
            
            # Convert to seconds based on suffix
            if suffix == 'm':
                value *= 60
            elif suffix == 'h':
                value *= 3600
            elif suffix == 'd':
                value *= 86400
            
            total_seconds += value
        
        # Simulate sleep
        time.sleep(min(total_seconds, 5))  # Cap at 5 seconds for simulation
        
        return ""
    
    @staticmethod
    def do_date(fs, cwd, arg):
        """
        Print or set the system date and time
        
        Usage: date [options] [+FORMAT]
        
        Options:
          -d, --date=STRING     Display time described by STRING, not 'now'
          -f, --file=DATEFILE   Like --date once for each line of DATEFILE
          -s, --set=STRING      Set time described by STRING
          -u, --utc, --universal  Print or set Coordinated Universal Time (UTC)
        """
        args = arg.split()
        
        # Parse options
        date_string = None
        date_file = None
        set_time = None
        use_utc = False
        format_str = None
        
        i = 0
        while i < len(args):
            if args[i].startswith('-d=') or args[i].startswith('--date='):
                date_string = args[i].split('=', 1)[1]
                i += 1
            elif args[i] == '-d' or args[i] == '--date':
                if i + 1 < len(args):
                    date_string = args[i+1]
                    i += 2
                else:
                    return "date: option requires an argument -- 'd'"
            elif args[i].startswith('-f=') or args[i].startswith('--file='):
                date_file = args[i].split('=', 1)[1]
                i += 1
            elif args[i] == '-f' or args[i] == '--file':
                if i + 1 < len(args):
                    date_file = args[i+1]
                    i += 2
                else:
                    return "date: option requires an argument -- 'f'"
            elif args[i].startswith('-s=') or args[i].startswith('--set='):
                set_time = args[i].split('=', 1)[1]
                i += 1
            elif args[i] == '-s' or args[i] == '--set':
                if i + 1 < len(args):
                    set_time = args[i+1]
                    i += 2
                else:
                    return "date: option requires an argument -- 's'"
            elif args[i] in ['-u', '--utc', '--universal']:
                use_utc = True
                i += 1
            elif args[i].startswith('+'):
                format_str = args[i][1:]
                i += 1
            else:
                return f"date: invalid option -- '{args[i]}'"
        
        # Handle date file
        if date_file:
            return "date: file option not implemented"
        
        # Handle set time
        if set_time:
            return "date: set time option not implemented"
        
        # Get current time
        if date_string:
            return "date: date string option not implemented"
        else:
            if use_utc:
                now = time.gmtime()
            else:
                now = time.localtime()
        
        # Format output
        if format_str:
            try:
                return time.strftime(format_str, now)
            except ValueError:
                return f"date: invalid format '{format_str}'"
        else:
            if use_utc:
                return time.strftime("%a %b %d %H:%M:%S UTC %Y", now)
            else:
                return time.strftime("%a %b %d %H:%M:%S %Z %Y", now)
    
    @staticmethod
    def do_crontab(fs, cwd, arg):
        """
        Maintain crontab files for individual users
        
        Usage: crontab [options] [file]
        
        Options:
          -l      List the current crontab
          -e      Edit the current crontab
          -r      Remove the current crontab
          -u user Specify user's crontab
        """
        args = arg.split()
        
        # Initialize crontab if not already
        if not hasattr(klayer, '_crontab'):
            klayer._crontab = {}
        
        # Parse options
        list_crontab = False
        edit_crontab = False
        remove_crontab = False
        user = os.getlogin()
        file_path = None
        
        i = 0
        while i < len(args):
            if args[i] == '-l':
                list_crontab = True
                i += 1
            elif args[i] == '-e':
                edit_crontab = True
                i += 1
            elif args[i] == '-r':
                remove_crontab = True
                i += 1
            elif args[i] == '-u':
                if i + 1 < len(args):
                    user = args[i+1]
                    i += 2
                else:
                    return "crontab: option requires an argument -- 'u'"
            else:
                file_path = args[i]
                i += 1
        
        # Can't specify multiple actions
        if sum([list_crontab, edit_crontab, remove_crontab, file_path is not None]) > 1:
            return "crontab: can't specify more than one of -l, -e, -r, or file"
        
        # Handle list crontab
        if list_crontab:
            if user not in klayer._crontab:
                return f"No crontab for {user}"
            
            return klayer._crontab[user]
        
        # Handle edit crontab
        if edit_crontab:
            # In a real implementation, would open an editor
            return "crontab: editing not implemented"
        
        # Handle remove crontab
        if remove_crontab:
            if user in klayer._crontab:
                del klayer._crontab[user]
                return f"crontab for {user} removed"
            else:
                return f"No crontab for {user}"
        
        # Handle install crontab from file
        if file_path:
            # Resolve path
            if not os.path.isabs(file_path):
                path = os.path.join(cwd, file_path)
            else:
                path = file_path
            
            # Check if file exists
            if not os.path.exists(path):
                return f"crontab: {file_path}: No such file or directory"
            
            # Read crontab file
            try:
                with open(path, 'r') as f:
                    crontab_content = f.read()
                
                klayer._crontab[user] = crontab_content
                return f"crontab: installing new crontab for {user}"
            except Exception as e:
                return f"crontab: error reading {file_path}: {str(e)}"
        
        # Default to list if no option specified
        if user not in klayer._crontab:
            return f"No crontab for {user}"
        
        return klayer._crontab[user]

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("jobs", UnixShellUtilities.do_jobs)
    shell.register_command("bg", UnixShellUtilities.do_bg)
    shell.register_command("fg", UnixShellUtilities.do_fg)
    shell.register_command("exec", UnixShellUtilities.do_exec)
    shell.register_command("export", UnixShellUtilities.do_export)
    shell.register_command("alias", UnixShellUtilities.do_alias)
    shell.register_command("unalias", UnixShellUtilities.do_unalias)
    shell.register_command("source", UnixShellUtilities.do_source)
    shell.register_command(".", UnixShellUtilities.do_source)  # Alias for source
    shell.register_command("history", UnixShellUtilities.do_history)
    shell.register_command("echo", UnixShellUtilities.do_echo)
    shell.register_command("sleep", UnixShellUtilities.do_sleep)
    shell.register_command("date", UnixShellUtilities.do_date)
    shell.register_command("crontab", UnixShellUtilities.do_crontab)

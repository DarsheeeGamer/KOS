"""
Process Accounting Utilities for KOS Shell

This module provides Unix-like accounting utilities for KOS.
"""

import os
import sys
import json
import time
import logging
import shlex
import datetime
from typing import Dict, List, Any, Optional

# Import KOS components
from kos.security.process_accounting import ProcessAccounting, Auditing
from kos.security.users import UserManager

# Set up logging
logger = logging.getLogger('KOS.shell.commands.accounting_utils')

class AccountingUtilities:
    """Process accounting commands for KOS shell"""
    
    @staticmethod
    def do_lastcomm(fs, cwd, arg):
        """
        Show previously executed commands
        
        Usage: lastcomm [options] [command] [user]
        
        Options:
          -f FILE              Use specified accounting file
          --user=USER          Show commands by specified user
          --tty=TTY            Show commands on specified terminal
          --host=HOST          Show commands on specified hostname
          -s, --strict         Require exact command name match
        """
        args = shlex.split(arg)
        
        # Parse options
        accounting_file = None
        user_filter = None
        tty_filter = None
        host_filter = None
        strict_match = False
        command_filter = None
        
        i = 0
        while i < len(args):
            if args[i] == "-f" and i + 1 < len(args):
                accounting_file = args[i+1]
                i += 2
            elif args[i].startswith("--user="):
                user_filter = args[i][7:]
                i += 1
            elif args[i].startswith("--tty="):
                tty_filter = args[i][6:]
                i += 1
            elif args[i].startswith("--host="):
                host_filter = args[i][7:]
                i += 1
            elif args[i] in ["-s", "--strict"]:
                strict_match = True
                i += 1
            else:
                # First unprocessed arg is command, second is user
                if command_filter is None:
                    command_filter = args[i]
                elif user_filter is None:
                    user_filter = args[i]
                i += 1
        
        # Handle user filter
        uid = None
        if user_filter:
            # Try to resolve user name to UID
            try:
                uid = int(user_filter)
            except ValueError:
                user = UserManager.get_user_by_name(user_filter)
                if user:
                    uid = user.uid
                else:
                    return f"lastcomm: unknown user: {user_filter}"
        
        # Read accounting records
        records = ProcessAccounting.read_records(
            accounting_file=accounting_file,
            uid=uid,
            command_filter=command_filter if command_filter and not strict_match else None
        )
        
        # Apply additional filters
        if command_filter and strict_match:
            # In strict mode, command must match exactly (not just contain)
            records = [r for r in records if r.command.split()[0] == command_filter]
        
        if tty_filter:
            # This is a mock implementation since we don't track TTY in our records
            pass
        
        if host_filter:
            records = [r for r in records if r.hostname == host_filter]
        
        # Sort by end time (most recent first)
        records.sort(key=lambda r: r.end_time if r.end_time else float('inf'), reverse=True)
        
        # Format output
        output = []
        for record in records:
            user = UserManager.get_user_by_uid(record.uid)
            username = user.username if user else f"uid:{record.uid}"
            
            cmd = record.command.split()[0] if record.command else "?"
            cmd_args = " ".join(record.command.split()[1:]) if record.command and len(record.command.split()) > 1 else ""
            
            # Format execution time
            exec_time = "???"
            if record.end_time and record.start_time:
                exec_time = f"{record.end_time - record.start_time:.2f}s"
            
            # Format CPU time
            cpu_time = f"{record.cpu_time:.2f}s" if record.cpu_time else "???"
            
            output.append(f"{cmd:<10} {username:<8} {cpu_time:<6} {exec_time:<6} {cmd_args}")
        
        if not output:
            return "No accounting records found"
        
        return "\n".join(output)
    
    @staticmethod
    def do_sa(fs, cwd, arg):
        """
        Summarize accounting information
        
        Usage: sa [options]
        
        Options:
          -a                   List all commands, not just totals
          -c                   Sort by total CPU time
          -d                   Sort by average CPU time
          -k                   Sort by CPU time percentage
          -m                   Sort by memory usage
          -r                   Reverse sort order
          -u                   Summarize by user
          -v                   Print verbose output
        """
        args = shlex.split(arg)
        
        # Parse options
        list_all = "-a" in args
        sort_by_cpu = "-c" in args
        sort_by_avg_cpu = "-d" in args
        sort_by_cpu_pct = "-k" in args
        sort_by_memory = "-m" in args
        reverse_sort = "-r" in args
        by_user = "-u" in args
        verbose = "-v" in args
        
        # Generate summary
        success, message, summary = ProcessAccounting.generate_summary()
        
        if not success:
            return message
        
        # Format output
        output = ["Process Accounting Summary:"]
        
        # Time period
        start_time = datetime.datetime.fromtimestamp(summary["time_period"]["start"]).strftime("%Y-%m-%d %H:%M:%S")
        end_time = datetime.datetime.fromtimestamp(summary["time_period"]["end"]).strftime("%Y-%m-%d %H:%M:%S")
        output.append(f"Time Period: {start_time} to {end_time}")
        output.append(f"Total Records: {summary['total_records']}")
        output.append("")
        
        # Totals
        cpu_time = summary["totals"]["cpu_time"]
        memory_usage = summary["totals"]["memory_usage"]
        io_read = summary["totals"]["io_read"]
        io_write = summary["totals"]["io_write"]
        
        output.append(f"Total CPU Time: {cpu_time:.2f}s")
        output.append(f"Total Memory Usage: {memory_usage:,} KB")
        output.append(f"Total I/O Read: {io_read:,} bytes")
        output.append(f"Total I/O Write: {io_write:,} bytes")
        output.append("")
        
        if by_user:
            # Summary by user
            output.append("User Summary:")
            
            # Prepare user data for sorting
            user_data = []
            for uid_str, user_info in summary["users"].items():
                user_data.append({
                    "uid": int(uid_str),
                    "username": user_info["username"],
                    "command_count": user_info["command_count"],
                    "cpu_time": user_info["cpu_time"],
                    "avg_cpu_time": user_info["cpu_time"] / user_info["command_count"] if user_info["command_count"] > 0 else 0,
                    "cpu_pct": (user_info["cpu_time"] / cpu_time * 100) if cpu_time > 0 else 0,
                    "memory_usage": user_info["memory_usage"],
                    "io_read": user_info["io_read"],
                    "io_write": user_info["io_write"]
                })
            
            # Sort user data
            if sort_by_cpu:
                user_data.sort(key=lambda x: x["cpu_time"], reverse=not reverse_sort)
            elif sort_by_avg_cpu:
                user_data.sort(key=lambda x: x["avg_cpu_time"], reverse=not reverse_sort)
            elif sort_by_cpu_pct:
                user_data.sort(key=lambda x: x["cpu_pct"], reverse=not reverse_sort)
            elif sort_by_memory:
                user_data.sort(key=lambda x: x["memory_usage"], reverse=not reverse_sort)
            else:
                # Default sort by username
                user_data.sort(key=lambda x: x["username"], reverse=reverse_sort)
            
            # Format user data
            for user in user_data:
                if verbose:
                    output.append(f"{user['username']:<8} CPU: {user['cpu_time']:.2f}s ({user['cpu_pct']:.1f}%) "
                                 f"Cmds: {user['command_count']} Avg: {user['avg_cpu_time']:.2f}s "
                                 f"Mem: {user['memory_usage']:,} KB")
                    
                    # Show top commands for this user
                    user_info = summary["users"][str(user["uid"])]
                    cmd_items = sorted(user_info["commands"].items(), key=lambda x: x[1], reverse=True)
                    for cmd, count in cmd_items[:5]:  # Show top 5 commands
                        output.append(f"  {cmd}: {count} executions")
                else:
                    output.append(f"{user['username']:<8} CPU: {user['cpu_time']:.2f}s ({user['cpu_pct']:.1f}%) "
                                 f"Cmds: {user['command_count']}")
        else:
            # Summary by command
            output.append("Command Summary:")
            
            # Prepare command data for sorting
            cmd_data = []
            for cmd, cmd_info in summary["commands"].items():
                cmd_data.append({
                    "command": cmd,
                    "count": cmd_info["count"],
                    "cpu_time": cmd_info["cpu_time"],
                    "avg_cpu_time": cmd_info["cpu_time"] / cmd_info["count"] if cmd_info["count"] > 0 else 0,
                    "cpu_pct": (cmd_info["cpu_time"] / cpu_time * 100) if cpu_time > 0 else 0,
                    "memory_usage": cmd_info["memory_usage"],
                    "io_read": cmd_info["io_read"],
                    "io_write": cmd_info["io_write"]
                })
            
            # Sort command data
            if sort_by_cpu:
                cmd_data.sort(key=lambda x: x["cpu_time"], reverse=not reverse_sort)
            elif sort_by_avg_cpu:
                cmd_data.sort(key=lambda x: x["avg_cpu_time"], reverse=not reverse_sort)
            elif sort_by_cpu_pct:
                cmd_data.sort(key=lambda x: x["cpu_pct"], reverse=not reverse_sort)
            elif sort_by_memory:
                cmd_data.sort(key=lambda x: x["memory_usage"], reverse=not reverse_sort)
            else:
                # Default sort by count
                cmd_data.sort(key=lambda x: x["count"], reverse=not reverse_sort)
            
            # Format command data
            if not list_all:
                # Only show summary of all commands
                cmd_count = sum(cmd["count"] for cmd in cmd_data)
                avg_cpu = cpu_time / cmd_count if cmd_count > 0 else 0
                
                output.append(f"{'TOTALS':<10} count: {cmd_count:<6} cpu: {cpu_time:.2f}s avg: {avg_cpu:.2f}s")
            else:
                # Show details for each command
                for cmd in cmd_data:
                    if verbose:
                        output.append(f"{cmd['command']:<10} count: {cmd['count']:<6} cpu: {cmd['cpu_time']:.2f}s "
                                     f"avg: {cmd['avg_cpu_time']:.2f}s %cpu: {cmd['cpu_pct']:.1f}% "
                                     f"mem: {cmd['memory_usage']:,} KB")
                    else:
                        output.append(f"{cmd['command']:<10} count: {cmd['count']:<6} cpu: {cmd['cpu_time']:.2f}s "
                                     f"avg: {cmd['avg_cpu_time']:.2f}s")
        
        return "\n".join(output)
    
    @staticmethod
    def do_accton(fs, cwd, arg):
        """
        Turn process accounting on or off
        
        Usage: accton [file | on | off]
        """
        args = shlex.split(arg)
        
        if not args:
            # Show current status
            if ProcessAccounting.is_accounting_enabled():
                return "Process accounting is currently enabled"
            else:
                return "Process accounting is currently disabled"
        
        action = args[0].lower()
        
        if action == "on":
            success, message = ProcessAccounting.enable_accounting()
            return message
        elif action == "off":
            success, message = ProcessAccounting.disable_accounting()
            return message
        else:
            # Assume it's a file path
            success, message = ProcessAccounting.enable_accounting(accounting_file=action)
            return message
    
    @staticmethod
    def do_acctcom(fs, cwd, arg):
        """
        Search for and print process accounting records
        
        Usage: acctcom [options]
        
        Options:
          -f FILE              Use specified accounting file
          -u USER              Show commands executed by USER
          -t START,END         Select records from time period
          -S TIME              Select records since TIME
          -E TIME              Select records until TIME
          -n PATTERN           Select commands matching PATTERN
          -h                   Show header
          -o FMT               Specify output format (JSON or human)
        """
        args = shlex.split(arg)
        
        # Parse options
        accounting_file = None
        user_filter = None
        start_time = None
        end_time = None
        pattern = None
        show_header = False
        output_format = "human"
        
        i = 0
        while i < len(args):
            if args[i] == "-f" and i + 1 < len(args):
                accounting_file = args[i+1]
                i += 2
            elif args[i] == "-u" and i + 1 < len(args):
                user_filter = args[i+1]
                i += 2
            elif args[i] == "-t" and i + 1 < len(args):
                time_parts = args[i+1].split(",")
                if len(time_parts) == 2:
                    try:
                        start_time = float(time_parts[0])
                        end_time = float(time_parts[1])
                    except ValueError:
                        return "acctcom: invalid time format"
                else:
                    return "acctcom: invalid time format, use START,END"
                i += 2
            elif args[i] == "-S" and i + 1 < len(args):
                try:
                    start_time = float(args[i+1])
                except ValueError:
                    return "acctcom: invalid time format"
                i += 2
            elif args[i] == "-E" and i + 1 < len(args):
                try:
                    end_time = float(args[i+1])
                except ValueError:
                    return "acctcom: invalid time format"
                i += 2
            elif args[i] == "-n" and i + 1 < len(args):
                pattern = args[i+1]
                i += 2
            elif args[i] == "-h":
                show_header = True
                i += 1
            elif args[i] == "-o" and i + 1 < len(args):
                output_format = args[i+1].lower()
                if output_format not in ["json", "human"]:
                    return "acctcom: invalid output format, use 'json' or 'human'"
                i += 2
            else:
                i += 1
        
        # Handle user filter
        uid = None
        if user_filter:
            # Try to resolve user name to UID
            try:
                uid = int(user_filter)
            except ValueError:
                user = UserManager.get_user_by_name(user_filter)
                if user:
                    uid = user.uid
                else:
                    return f"acctcom: unknown user: {user_filter}"
        
        # Read accounting records
        records = ProcessAccounting.read_records(
            accounting_file=accounting_file,
            start_time=start_time,
            end_time=end_time,
            uid=uid,
            command_filter=pattern
        )
        
        if not records:
            return "No accounting records found"
        
        # Format output
        if output_format == "json":
            return json.dumps([r.to_dict() for r in records], indent=2)
        else:
            output = []
            
            if show_header:
                output.append("COMMAND      USER      STARTED                  ENDED                    CPU      MEM       EXIT")
                output.append("-" * 80)
            
            for record in records:
                user = UserManager.get_user_by_uid(record.uid)
                username = user.username if user else f"uid:{record.uid}"
                
                cmd = record.command.split()[0] if record.command else "?"
                
                # Format times
                start_str = datetime.datetime.fromtimestamp(record.start_time).strftime("%Y-%m-%d %H:%M:%S")
                end_str = "RUNNING" if record.end_time is None else datetime.datetime.fromtimestamp(record.end_time).strftime("%Y-%m-%d %H:%M:%S")
                
                # Format CPU time and exit code
                cpu_str = f"{record.cpu_time:.2f}s" if record.cpu_time is not None else "?"
                mem_str = f"{record.memory_usage:,}" if record.memory_usage is not None else "?"
                exit_str = str(record.exit_code) if record.exit_code is not None else "?"
                
                output.append(f"{cmd:<12} {username:<8} {start_str:<24} {end_str:<24} {cpu_str:<8} {mem_str:<8} {exit_str}")
            
            return "\n".join(output)
    
    @staticmethod
    def do_auditctl(fs, cwd, arg):
        """
        Control the audit system
        
        Usage: auditctl [options]
        
        Options:
          -e [0|1|2]           Enable or disable auditing (0=off, 1=on, 2=locked)
          -l                   List all rules
          -s                   Report audit system status
          -f [0|1|2]           Set failure mode
        """
        args = shlex.split(arg)
        
        if not args:
            return AccountingUtilities.do_auditctl.__doc__
        
        # Parse options
        i = 0
        while i < len(args):
            if args[i] == "-e" and i + 1 < len(args):
                mode = args[i+1]
                if mode == "0":
                    success, message = Auditing.disable_auditing()
                    return message
                elif mode == "1":
                    success, message = Auditing.enable_auditing()
                    return message
                elif mode == "2":
                    return "auditctl: locked mode not supported"
                else:
                    return "auditctl: invalid mode, use 0, 1, or 2"
                i += 2
            elif args[i] == "-l":
                return "No audit rules defined (not supported in this version)"
            elif args[i] == "-s":
                status = "enabled" if Auditing.is_auditing_enabled() else "disabled"
                return f"Audit status: {status}"
            elif args[i] == "-f" and i + 1 < len(args):
                return "auditctl: failure mode settings not supported in this version"
            else:
                i += 1
        
        return "auditctl: no valid options specified"
    
    @staticmethod
    def do_ausearch(fs, cwd, arg):
        """
        Search audit logs
        
        Usage: ausearch [options]
        
        Options:
          -f FILE              Use specified audit file
          -ts START            Search from specified time
          -te END              Search to specified time
          -m TYPE              Search for event type
          -ui UID              Search for user ID
          -ua USER             Search for user name
          -i                   Interpret numeric values
          -x TEXT              Search for text
          -n LIMIT             Limit results
        """
        args = shlex.split(arg)
        
        # Parse options
        audit_file = None
        start_time = None
        end_time = None
        event_type = None
        uid = None
        search_text = None
        interpret = False
        limit = None
        
        i = 0
        while i < len(args):
            if args[i] == "-f" and i + 1 < len(args):
                audit_file = args[i+1]
                i += 2
            elif args[i] == "-ts" and i + 1 < len(args):
                try:
                    # Support both numeric and date formats
                    time_arg = args[i+1]
                    if time_arg.replace(".", "").isdigit():
                        start_time = float(time_arg)
                    else:
                        # Simple date parsing
                        start_time = time.mktime(datetime.datetime.strptime(time_arg, "%Y-%m-%d %H:%M:%S").timetuple())
                except ValueError:
                    return "ausearch: invalid time format"
                i += 2
            elif args[i] == "-te" and i + 1 < len(args):
                try:
                    time_arg = args[i+1]
                    if time_arg.replace(".", "").isdigit():
                        end_time = float(time_arg)
                    else:
                        end_time = time.mktime(datetime.datetime.strptime(time_arg, "%Y-%m-%d %H:%M:%S").timetuple())
                except ValueError:
                    return "ausearch: invalid time format"
                i += 2
            elif args[i] == "-m" and i + 1 < len(args):
                event_type = args[i+1]
                i += 2
            elif args[i] == "-ui" and i + 1 < len(args):
                try:
                    uid = int(args[i+1])
                except ValueError:
                    return "ausearch: invalid user ID"
                i += 2
            elif args[i] == "-ua" and i + 1 < len(args):
                user = UserManager.get_user_by_name(args[i+1])
                if user:
                    uid = user.uid
                else:
                    return f"ausearch: unknown user: {args[i+1]}"
                i += 2
            elif args[i] == "-i":
                interpret = True
                i += 1
            elif args[i] == "-x" and i + 1 < len(args):
                search_text = args[i+1]
                i += 2
            elif args[i] == "-n" and i + 1 < len(args):
                try:
                    limit = int(args[i+1])
                except ValueError:
                    return "ausearch: invalid limit"
                i += 2
            else:
                i += 1
        
        # Search events
        if search_text:
            events = Auditing.search_events(
                search_term=search_text,
                audit_file=audit_file,
                start_time=start_time,
                end_time=end_time,
                max_events=limit
            )
        else:
            events = Auditing.read_events(
                audit_file=audit_file,
                start_time=start_time,
                end_time=end_time,
                uid=uid,
                event_type=event_type,
                max_events=limit
            )
        
        if not events:
            return "No audit records found"
        
        # Format output
        output = []
        for event in events:
            user = UserManager.get_user_by_uid(event.uid)
            username = user.username if user else f"uid:{event.uid}"
            
            time_str = datetime.datetime.fromtimestamp(event.timestamp).strftime("%Y-%m-%d %H:%M:%S")
            result = "success" if event.success else "failed"
            
            output.append(f"type={event.event_type} time={time_str} user={username} result={result}")
            
            # Format details
            if event.details:
                for key, value in event.details.items():
                    if interpret and isinstance(value, int) and key in ["uid", "gid", "pid"]:
                        if key == "uid" or key == "gid":
                            # Try to resolve user/group names
                            if key == "uid":
                                user = UserManager.get_user_by_uid(value)
                                if user:
                                    value = f"{value}({user.username})"
                            # Group resolution would be here
                    
                    output.append(f"  {key}={value}")
            
            output.append("")
        
        return "\n".join(output)

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("lastcomm", AccountingUtilities.do_lastcomm)
    shell.register_command("sa", AccountingUtilities.do_sa)
    shell.register_command("accton", AccountingUtilities.do_accton)
    shell.register_command("acctcom", AccountingUtilities.do_acctcom)
    shell.register_command("auditctl", AccountingUtilities.do_auditctl)
    shell.register_command("ausearch", AccountingUtilities.do_ausearch)

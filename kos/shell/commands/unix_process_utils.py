"""
Unix-like Process Management Utilities for KOS Shell

This module provides Linux/Unix-like process management commands for KOS.
"""

import os
import sys
import time
import signal
import logging
import psutil
import pwd
import grp
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

# Import KOS components
from kos.layer import klayer
from kos.advlayer import kadvlayer

# Set up logging
logger = logging.getLogger('KOS.shell.commands.unix_process_utils')

class UnixProcessUtilities:
    """Unix-like process management commands for KOS shell"""
    
    @staticmethod
    def do_ps(fs, cwd, arg):
        """
        Report process status
        
        Usage: ps [options]
        
        Options:
          -e, --everyone        Display information about other users' processes
          -f, --full            Full listing
          -l, --long            Long listing
          -a, --all             Show all processes
          -u, --user=USER       Show processes for specified user
          -x                    Show processes without controlling terminals
          --sort=COLUMN         Sort by specified column
        """
        args = arg.split()
        
        # Parse options
        show_everyone = False
        full_listing = False
        long_listing = False
        show_all = False
        show_user = None
        show_without_terminal = False
        sort_column = 'pid'  # Default sort by PID
        
        # Process arguments
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                if args[i] in ['-e', '--everyone']:
                    show_everyone = True
                elif args[i] in ['-f', '--full']:
                    full_listing = True
                elif args[i] in ['-l', '--long']:
                    long_listing = True
                elif args[i] in ['-a', '--all']:
                    show_all = True
                elif args[i] in ['-x']:
                    show_without_terminal = True
                elif args[i].startswith('--sort='):
                    sort_column = args[i].split('=')[1].lower()
                elif args[i].startswith('-u=') or args[i].startswith('--user='):
                    show_user = args[i].split('=')[1]
                elif args[i] == '-u' or args[i] == '--user':
                    if i + 1 < len(args):
                        show_user = args[i+1]
                        i += 1
                    else:
                        return "ps: option requires an argument -- 'u'"
                else:
                    # Process combined options
                    for c in args[i][1:]:
                        if c == 'e':
                            show_everyone = True
                        elif c == 'f':
                            full_listing = True
                        elif c == 'l':
                            long_listing = True
                        elif c == 'a':
                            show_all = True
                        elif c == 'x':
                            show_without_terminal = True
            i += 1
        
        # Get processes
        processes = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'username', 'status', 'cpu_percent', 'memory_percent', 'create_time', 'cmdline', 'ppid']):
                # Skip processes not matching criteria
                if not show_everyone and proc.info['username'] != os.getlogin():
                    continue
                if show_user and proc.info['username'] != show_user:
                    continue
                
                # Add process to list
                processes.append({
                    'pid': proc.info['pid'],
                    'ppid': proc.info['ppid'],
                    'name': proc.info['name'],
                    'username': proc.info['username'],
                    'status': proc.info['status'],
                    'cpu': proc.info['cpu_percent'],
                    'memory': proc.info['memory_percent'],
                    'start_time': proc.info['create_time'],
                    'cmdline': ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else '[' + proc.info['name'] + ']'
                })
        except Exception as e:
            return f"ps: error getting process information: {str(e)}"
        
        # Sort processes
        if sort_column in ['pid', 'ppid', 'name', 'username', 'status', 'cpu', 'memory', 'start_time', 'cmdline']:
            processes.sort(key=lambda p: p[sort_column])
        else:
            return f"ps: invalid sort column: {sort_column}"
        
        # Format output
        results = []
        
        if full_listing:
            # Full listing format
            results.append("UID        PID  PPID  C    STIME TTY      STAT TIME     CMD")
            
            for proc in processes:
                # Format time
                start_time = datetime.fromtimestamp(proc['start_time']).strftime('%H:%M:%S')
                
                # Format state
                state = proc['status'][0].upper()
                
                results.append(f"{proc['username']:<9} {proc['pid']:<5} {proc['ppid']:<5} {proc['cpu']:<4.1f} {start_time} ?        {state}    00:00:00 {proc['cmdline']}")
        
        elif long_listing:
            # Long listing format
            results.append("F S   UID   PID  PPID  C PRI  NI ADDR SZ WCHAN  TTY          TIME CMD")
            
            for proc in processes:
                # Format state
                state = proc['status'][0].upper()
                
                results.append(f"0 {state} {proc['username']:<5} {proc['pid']:<5} {proc['ppid']:<5} {proc['cpu']:<2.0f}  80   0 -     - -      ?        00:00:00 {proc['cmdline']}")
        
        else:
            # Default format
            results.append("  PID TTY          TIME CMD")
            
            for proc in processes:
                results.append(f"{proc['pid']:<5} ?        00:00:00 {proc['cmdline']}")
        
        return "\n".join(results)
    
    @staticmethod
    def do_kill(fs, cwd, arg):
        """
        Terminate or signal processes
        
        Usage: kill [options] PID...
        
        Options:
          -s, --signal=SIGNAL   Send specified signal instead of SIGTERM
          -l, --list            List signal names
        """
        args = arg.split()
        
        # Parse options
        signal_name = 'SIGTERM'  # Default signal
        list_signals = False
        
        # Process arguments
        pids = []
        
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                if args[i] in ['-l', '--list']:
                    list_signals = True
                elif args[i].startswith('-s=') or args[i].startswith('--signal='):
                    signal_name = args[i].split('=')[1]
                elif args[i] == '-s' or args[i] == '--signal':
                    if i + 1 < len(args):
                        signal_name = args[i+1]
                        i += 1
                    else:
                        return "kill: option requires an argument -- 's'"
                elif args[i].startswith('-'):
                    # Check if it's a signal number prefixed with -
                    try:
                        signal_num = int(args[i][1:])
                        signal_name = signal_num
                    except ValueError:
                        return f"kill: invalid option -- '{args[i]}'"
            else:
                try:
                    pids.append(int(args[i]))
                except ValueError:
                    return f"kill: {args[i]}: arguments must be process or job IDs"
            i += 1
        
        # List signals if requested
        if list_signals:
            signals = []
            for sig_name in dir(signal):
                if sig_name.startswith('SIG') and not sig_name.startswith('SIG_'):
                    sig_num = getattr(signal, sig_name)
                    signals.append(f"{sig_num}) {sig_name}")
            return "\n".join(signals)
        
        # Check if PIDs are specified
        if not pids:
            return "kill: no process ID specified\nTry 'kill --help' for more information."
        
        # Convert signal name to number if necessary
        signal_num = None
        try:
            if isinstance(signal_name, int):
                signal_num = signal_name
            elif signal_name.isdigit():
                signal_num = int(signal_name)
            elif signal_name.startswith('SIG'):
                signal_num = getattr(signal, signal_name)
            else:
                signal_num = getattr(signal, 'SIG' + signal_name)
        except (AttributeError, ValueError):
            return f"kill: invalid signal: {signal_name}"
        
        # Kill processes
        results = []
        
        for pid in pids:
            try:
                process = psutil.Process(pid)
                process.send_signal(signal_num)
            except psutil.NoSuchProcess:
                results.append(f"kill: ({pid}) - No such process")
            except psutil.AccessDenied:
                results.append(f"kill: ({pid}) - Operation not permitted")
            except Exception as e:
                results.append(f"kill: ({pid}) - {str(e)}")
        
        if results:
            return "\n".join(results)
        return ""  # Success with no output
    
    @staticmethod
    def do_top(fs, cwd, arg):
        """
        Display Linux processes
        
        Usage: top [options]
        
        Options:
          -n, --iterations=N    Number of iterations before terminating
          -d, --delay=N         Delay time between updates in seconds
          -b, --batch           Run in batch mode (no interactive display)
          -p, --pid=PID         Monitor only process with specified PID
        """
        args = arg.split()
        
        # Parse options
        iterations = 1  # Run once by default
        delay = 3.0  # Default delay in seconds
        batch_mode = True  # Always batch mode for this implementation
        monitor_pid = None
        
        # Process arguments
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                if args[i].startswith('-n=') or args[i].startswith('--iterations='):
                    try:
                        iterations = int(args[i].split('=')[1])
                    except ValueError:
                        return f"top: invalid iterations: '{args[i].split('=')[1]}'"
                elif args[i].startswith('-d=') or args[i].startswith('--delay='):
                    try:
                        delay = float(args[i].split('=')[1])
                    except ValueError:
                        return f"top: invalid delay: '{args[i].split('=')[1]}'"
                elif args[i].startswith('-p=') or args[i].startswith('--pid='):
                    try:
                        monitor_pid = int(args[i].split('=')[1])
                    except ValueError:
                        return f"top: invalid PID: '{args[i].split('=')[1]}'"
                elif args[i] == '-n' or args[i] == '--iterations':
                    if i + 1 < len(args):
                        try:
                            iterations = int(args[i+1])
                            i += 1
                        except ValueError:
                            return f"top: invalid iterations: '{args[i+1]}'"
                    else:
                        return "top: option requires an argument -- 'n'"
                elif args[i] == '-d' or args[i] == '--delay':
                    if i + 1 < len(args):
                        try:
                            delay = float(args[i+1])
                            i += 1
                        except ValueError:
                            return f"top: invalid delay: '{args[i+1]}'"
                    else:
                        return "top: option requires an argument -- 'd'"
                elif args[i] == '-p' or args[i] == '--pid':
                    if i + 1 < len(args):
                        try:
                            monitor_pid = int(args[i+1])
                            i += 1
                        except ValueError:
                            return f"top: invalid PID: '{args[i+1]}'"
                    else:
                        return "top: option requires an argument -- 'p'"
                elif args[i] in ['-b', '--batch']:
                    batch_mode = True
            i += 1
        
        # For this implementation, we'll just run once and return static data
        results = []
        
        # Get system info
        results.append(f"top - {datetime.now().strftime('%H:%M:%S')} up 0 days,  0:00,  1 user,  load average: 0.00, 0.00, 0.00")
        results.append(f"Tasks: {len(list(psutil.process_iter()))} total,   1 running, {len(list(psutil.process_iter())) - 1} sleeping,   0 stopped,   0 zombie")
        
        # Get CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.1)
        results.append(f"%Cpu(s): {cpu_percent:.1f} us,  {100-cpu_percent:.1f} sy,  0.0 ni, 0.0 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st")
        
        # Get memory usage
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        results.append(f"MiB Mem :  {mem.total/1024/1024:.1f} total,  {mem.available/1024/1024:.1f} free,  {mem.used/1024/1024:.1f} used,  {mem.cached/1024/1024:.1f} buff/cache")
        results.append(f"MiB Swap:  {swap.total/1024/1024:.1f} total,  {swap.free/1024/1024:.1f} free,  {swap.used/1024/1024:.1f} used.  {mem.available/1024/1024:.1f} avail Mem")
        
        # Add header for process list
        results.append("\n   PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND")
        
        # Get processes
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'username', 'status', 'cpu_percent', 'memory_percent', 'memory_info', 'create_time', 'cmdline']):
            if monitor_pid is not None and proc.info['pid'] != monitor_pid:
                continue
            
            # Get memory info
            try:
                mem_info = proc.info['memory_info']
                virt = mem_info.vms / 1024  # KB
                res = mem_info.rss / 1024   # KB
                shr = 0  # Not available in psutil
            except:
                virt = 0
                res = 0
                shr = 0
            
            # Add process to list
            processes.append({
                'pid': proc.info['pid'],
                'username': proc.info['username'],
                'status': proc.info['status'][0].upper(),
                'cpu': proc.info['cpu_percent'],
                'memory': proc.info['memory_percent'],
                'virt': virt,
                'res': res,
                'shr': shr,
                'name': proc.info['name'],
                'cmdline': ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else proc.info['name']
            })
        
        # Sort processes by CPU usage
        processes.sort(key=lambda p: p['cpu'], reverse=True)
        
        # Add processes to output
        for proc in processes[:20]:  # Only show top 20
            results.append(f"{proc['pid']:6d} {proc['username']:<9} 20   0 {proc['virt']:8.0f} {proc['res']:6.0f} {proc['shr']:6.0f} {proc['status']} {proc['cpu']:5.1f} {proc['memory']:5.1f}   0:00.00 {proc['cmdline']}")
        
        return "\n".join(results)

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("ps", UnixProcessUtilities.do_ps)
    shell.register_command("kill", UnixProcessUtilities.do_kill)
    shell.register_command("top", UnixProcessUtilities.do_top)

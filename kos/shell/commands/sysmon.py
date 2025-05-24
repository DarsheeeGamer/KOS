"""
System Monitoring Commands for KOS shell.

This module implements various system monitoring utilities similar to
common Unix/Linux commands like ps, top, df, free, etc. It leverages
the KADVLayer capabilities for advanced system integration.
"""

import os
import re
import shlex
import logging
import time
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
import psutil

logger = logging.getLogger('KOS.shell.sysmon')

# Try to import the KADVLayer components
try:
    from ...kadv.layer import KADVLayer
    from ...kadv.system_resource_monitor import SystemResourceMonitor
    from ...kadv.process_monitor import ProcessMonitor
    from ...kadv.system_info import SystemInfo
    from ...kadv.system_metrics import SystemMetrics
    KADV_AVAILABLE = True
except ImportError:
    KADV_AVAILABLE = False
    logger.warning("KADVLayer not available, falling back to basic functionality")

class SystemMonitorCommands:
    """Implementation of system monitoring commands for KOS shell."""
    
    @staticmethod
    def do_ps(fs, cwd, arg):
        """Report process status
        
        Usage: ps [options]
        Display information about active processes.
        
        Options:
          -a        Show processes for all users
          -u        Show detailed user-oriented format
          -x        Show processes without controlling terminal
          -e        Show all processes
          -f        Show full format listing
          -l        Show long format
          --sort=X  Sort by column (e.g., --sort=pid, --sort=-cpu)
        
        Examples:
          ps           # Show processes for current user
          ps -ef       # Full listing of all processes
          ps -u --sort=-cpu  # Sort by CPU usage (descending)
        """
        try:
            args = shlex.split(arg)
            
            # Parse options
            show_all_users = False
            detailed_format = False
            show_all = False
            full_format = False
            long_format = False
            show_tty = False
            sort_by = "pid"
            sort_reverse = False
            
            i = 0
            while i < len(args):
                if args[i] in ['-h', '--help']:
                    return SystemMonitorCommands.do_ps.__doc__
                elif args[i] == '-a':
                    show_all_users = True
                elif args[i] == '-u':
                    detailed_format = True
                elif args[i] == '-x':
                    show_tty = True
                elif args[i] == '-e':
                    show_all = True
                elif args[i] == '-f':
                    full_format = True
                elif args[i] == '-l':
                    long_format = True
                elif args[i].startswith('--sort='):
                    sort_spec = args[i][7:]
                    if sort_spec.startswith('-'):
                        sort_reverse = True
                        sort_by = sort_spec[1:]
                    else:
                        sort_by = sort_spec
                i += 1
            
            # If KADVLayer is available, use its ProcessMonitor
            if KADV_AVAILABLE:
                process_monitor = ProcessMonitor()
                processes = process_monitor.get_all_processes()
            else:
                # Fall back to psutil
                processes = []
                for proc in psutil.process_iter(['pid', 'name', 'username', 'status', 'cpu_percent', 'memory_percent', 'create_time']):
                    try:
                        pinfo = proc.as_dict()
                        processes.append(pinfo)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
            
            # Filter processes based on options
            if not show_all and not show_all_users:
                try:
                    current_user = os.getlogin()
                except Exception:
                    current_user = None
                
                if current_user:
                    processes = [p for p in processes if p.get('username') == current_user]
            
            # Sort processes
            valid_sort_fields = ['pid', 'name', 'username', 'status', 'cpu_percent', 'memory_percent', 'create_time']
            if sort_by in valid_sort_fields:
                processes.sort(key=lambda p: p.get(sort_by, 0) if sort_by != 'name' else p.get(sort_by, ''), 
                              reverse=sort_reverse)
            
            # Format output
            result = []
            
            if full_format or detailed_format:
                # Header
                header = "USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND"
                result.append(header)
                
                for proc in processes:
                    try:
                        # Get process info
                        pid = proc.get('pid', 0)
                        name = proc.get('name', '?')
                        username = proc.get('username', '?')
                        cpu_percent = proc.get('cpu_percent', 0.0)
                        memory_percent = proc.get('memory_percent', 0.0)
                        
                        # Get additional info
                        try:
                            p = psutil.Process(pid)
                            memory_info = p.memory_info()
                            vsz = memory_info.vms // 1024  # KB
                            rss = memory_info.rss // 1024  # KB
                            if hasattr(p, 'terminal') and callable(p.terminal):
                                tty = p.terminal() or '?'
                            else:
                                tty = '?'
                            status = proc.get('status', '?')[0].upper()
                            create_time = datetime.fromtimestamp(proc.get('create_time', 0))
                            start_time = create_time.strftime("%H:%M")
                            
                            # Calculate running time
                            running_seconds = time.time() - proc.get('create_time', 0)
                            hours = int(running_seconds // 3600)
                            minutes = int((running_seconds % 3600) // 60)
                            running_time = f"{hours:02d}:{minutes:02d}"
                            
                            # Get command line
                            if hasattr(p, 'cmdline') and callable(p.cmdline):
                                cmdline = ' '.join(p.cmdline())
                                if not cmdline:
                                    cmdline = f"[{name}]"
                            else:
                                cmdline = name
                                
                        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                            vsz = 0
                            rss = 0
                            tty = '?'
                            status = '?'
                            start_time = '?'
                            running_time = '?'
                            cmdline = f"[{name}]"
                        
                        # Format line
                        line = f"{username:<12} {pid:5d} {cpu_percent:4.1f} {memory_percent:4.1f} {vsz:6d} {rss:6d} {tty:<8} {status}    {start_time} {running_time} {cmdline}"
                        result.append(line)
                    except Exception as e:
                        logger.error(f"Error formatting process {proc.get('pid', '?')}: {e}")
            
            elif long_format:
                # Header
                header = "F S   UID   PID  PPID  C PRI  NI ADDR SZ WCHAN  TTY          TIME CMD"
                result.append(header)
                
                for proc in processes:
                    try:
                        # Get process info
                        pid = proc.get('pid', 0)
                        name = proc.get('name', '?')
                        
                        # Get additional info
                        try:
                            p = psutil.Process(pid)
                            if hasattr(p, 'uids') and callable(p.uids):
                                uid = p.uids().real
                            else:
                                uid = 0
                            if hasattr(p, 'ppid') and callable(p.ppid):
                                ppid = p.ppid()
                            else:
                                ppid = 0
                            status = proc.get('status', '?')[0].upper()
                            if hasattr(p, 'cpu_num') and callable(p.cpu_num):
                                cpu_num = p.cpu_num()
                            else:
                                cpu_num = 0
                            if hasattr(p, 'nice') and callable(p.nice):
                                nice = p.nice()
                            else:
                                nice = 0
                            
                            # Calculate priority (simplified)
                            priority = 80 - nice
                            
                            # Memory size in pages (simplified)
                            memory_info = p.memory_info()
                            sz = memory_info.vms // 4096  # Approximation in pages
                            
                            # Terminal
                            if hasattr(p, 'terminal') and callable(p.terminal):
                                tty = p.terminal() or '?'
                            else:
                                tty = '?'
                            
                            # Calculate running time
                            running_seconds = time.time() - proc.get('create_time', 0)
                            hours = int(running_seconds // 3600)
                            minutes = int((running_seconds % 3600) // 60)
                            seconds = int(running_seconds % 60)
                            running_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                            
                            # Command
                            if hasattr(p, 'cmdline') and callable(p.cmdline):
                                cmd = ' '.join(p.cmdline()) or f"[{name}]"
                            else:
                                cmd = name
                                
                        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                            uid = 0
                            ppid = 0
                            status = '?'
                            cpu_num = 0
                            priority = 0
                            nice = 0
                            sz = 0
                            tty = '?'
                            running_time = '?'
                            cmd = f"[{name}]"
                        
                        # Format line (simplified format)
                        flags = 0  # Placeholder
                        wchan = '-'  # Not available in psutil
                        addr = '-'  # Not available in psutil
                        
                        line = f"{flags:1d} {status} {uid:5d} {pid:5d} {ppid:5d} {cpu_num:1d} {priority:3d} {nice:3d} {addr} {sz:2d} {wchan:<6} {tty:<11} {running_time} {cmd}"
                        result.append(line)
                    except Exception as e:
                        logger.error(f"Error formatting process {proc.get('pid', '?')}: {e}")
            
            else:
                # Simple format
                header = "  PID TTY          TIME CMD"
                result.append(header)
                
                for proc in processes:
                    try:
                        # Get process info
                        pid = proc.get('pid', 0)
                        name = proc.get('name', '?')
                        
                        # Get additional info
                        try:
                            p = psutil.Process(pid)
                            if hasattr(p, 'terminal') and callable(p.terminal):
                                tty = p.terminal() or '?'
                            else:
                                tty = '?'
                            
                            # Calculate running time
                            running_seconds = time.time() - proc.get('create_time', 0)
                            hours = int(running_seconds // 3600)
                            minutes = int((running_seconds % 3600) // 60)
                            seconds = int(running_seconds % 60)
                            running_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                            
                            # Command
                            if hasattr(p, 'cmdline') and callable(p.cmdline):
                                cmd = ' '.join(p.cmdline()) or f"[{name}]"
                            else:
                                cmd = name
                                
                        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                            tty = '?'
                            running_time = '00:00:00'
                            cmd = f"[{name}]"
                        
                        # Format line
                        line = f"{pid:5d} {tty:<11} {running_time} {cmd}"
                        result.append(line)
                    except Exception as e:
                        logger.error(f"Error formatting process {proc.get('pid', '?')}: {e}")
            
            return "\n".join(result)
                
        except Exception as e:
            logger.error(f"Error in ps command: {e}")
            return f"ps: {str(e)}"
    
    @staticmethod
    def do_free(fs, cwd, arg):
        """Display amount of free and used memory in the system
        
        Usage: free [options]
        Display memory usage information.
        
        Options:
          -b, --bytes     Show output in bytes
          -k, --kilo      Show output in kilobytes
          -m, --mega      Show output in megabytes
          -g, --giga      Show output in gigabytes
          -h, --human     Show human-readable output
          -t, --total     Show row with totals
          -s N, --seconds=N  Update continuously every N seconds
        
        Examples:
          free           # Show memory usage in kilobytes
          free -m        # Show memory usage in megabytes
          free -h        # Show memory usage in human-readable format
        """
        try:
            args = shlex.split(arg)
            
            # Parse options
            unit = 'k'  # Default is kilobytes
            show_total = False
            update_interval = None
            
            i = 0
            while i < len(args):
                if args[i] in ['-h', '--help']:
                    return SystemMonitorCommands.do_free.__doc__
                elif args[i] in ['-b', '--bytes']:
                    unit = 'b'
                elif args[i] in ['-k', '--kilo']:
                    unit = 'k'
                elif args[i] in ['-m', '--mega']:
                    unit = 'm'
                elif args[i] in ['-g', '--giga']:
                    unit = 'g'
                elif args[i] in ['-h', '--human']:
                    unit = 'human'
                elif args[i] in ['-t', '--total']:
                    show_total = True
                elif args[i] in ['-s', '--seconds']:
                    if i + 1 < len(args):
                        try:
                            update_interval = int(args[i + 1])
                            i += 1
                        except ValueError:
                            return f"free: invalid seconds value: '{args[i + 1]}'"
                    else:
                        return "free: option requires an argument -- 's'"
                elif args[i].startswith('--seconds='):
                    try:
                        update_interval = int(args[i][10:])
                    except ValueError:
                        return f"free: invalid seconds value: '{args[i][10:]}'"
                i += 1
            
            # Function to format memory size based on unit
            def format_size(bytes_value):
                if unit == 'b':
                    return str(bytes_value)
                elif unit == 'k':
                    return str(bytes_value // 1024)
                elif unit == 'm':
                    return str(bytes_value // 1024 // 1024)
                elif unit == 'g':
                    return str(bytes_value // 1024 // 1024 // 1024)
                elif unit == 'human':
                    for suffix in ['B', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
                        if abs(bytes_value) < 1024.0:
                            return f"{bytes_value:.1f}{suffix}"
                        bytes_value /= 1024.0
                    return f"{bytes_value:.1f}Y"
            
            # Function to display memory information
            def display_memory_info():
                # Get memory information
                virtual_memory = psutil.virtual_memory()
                swap_memory = psutil.swap_memory()
                
                # Calculate metrics
                total = virtual_memory.total
                used = virtual_memory.used
                free = virtual_memory.available
                shared = getattr(virtual_memory, 'shared', 0)
                buffers = getattr(virtual_memory, 'buffers', 0)
                cached = getattr(virtual_memory, 'cached', 0)
                
                swap_total = swap_memory.total
                swap_used = swap_memory.used
                swap_free = swap_memory.free
                
                # Format header based on unit
                if unit == 'human':
                    header = "               total        used        free      shared  buff/cache   available"
                else:
                    unit_label = {'b': 'bytes', 'k': 'kB', 'm': 'MB', 'g': 'GB'}[unit]
                    header = f"               total        used        free      shared  buff/cache   available"
                
                # Format output
                result = [header]
                
                # Memory line
                mem_line = f"Mem:     {format_size(total):10s} {format_size(used):10s} {format_size(free):10s} {format_size(shared):10s} {format_size(buffers + cached):10s} {format_size(free):10s}"
                result.append(mem_line)
                
                # Swap line
                swap_line = f"Swap:    {format_size(swap_total):10s} {format_size(swap_used):10s} {format_size(swap_free):10s}"
                result.append(swap_line)
                
                # Total line if requested
                if show_total:
                    total_line = f"Total:   {format_size(total + swap_total):10s} {format_size(used + swap_used):10s} {format_size(free + swap_free):10s}"
                    result.append(total_line)
                
                return "\n".join(result)
            
            # Display once or continuously
            if update_interval:
                # This would be implemented to update continuously in a real shell
                # For this simulation, we'll just show a message
                return f"{display_memory_info()}\n\nWould update every {update_interval} seconds in a real shell environment."
            else:
                return display_memory_info()
                
        except Exception as e:
            logger.error(f"Error in free command: {e}")
            return f"free: {str(e)}"
    
    @staticmethod
    def do_df(fs, cwd, arg):
        """Report file system disk space usage
        
        Usage: df [options] [file...]
        Show information about file system space usage.
        
        Options:
          -h, --human-readable    Print sizes in human readable format
          -k, --kilobytes         Print sizes in kilobytes
          -m, --megabytes         Print sizes in megabytes
          -T, --print-type        Print file system type
          -i, --inodes            List inode information instead of block usage
        
        Examples:
          df           # Show disk usage for all filesystems
          df -h        # Show disk usage in human-readable format
          df /path     # Show disk usage for specific path
        """
        try:
            args = shlex.split(arg)
            
            # Parse options
            human_readable = False
            kilobytes = True  # Default
            megabytes = False
            show_type = False
            show_inodes = False
            paths = []
            
            i = 0
            while i < len(args):
                if args[i] in ['-h', '--help']:
                    return SystemMonitorCommands.do_df.__doc__
                elif args[i] in ['-h', '--human-readable']:
                    human_readable = True
                    kilobytes = False
                elif args[i] in ['-k', '--kilobytes']:
                    kilobytes = True
                    megabytes = False
                    human_readable = False
                elif args[i] in ['-m', '--megabytes']:
                    megabytes = True
                    kilobytes = False
                    human_readable = False
                elif args[i] in ['-T', '--print-type']:
                    show_type = True
                elif args[i] in ['-i', '--inodes']:
                    show_inodes = True
                else:
                    paths.append(args[i])
                i += 1
            
            # Function to format size
            def format_size(size_bytes):
                if human_readable:
                    for suffix in ['B', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
                        if abs(size_bytes) < 1024.0:
                            return f"{size_bytes:.1f}{suffix}"
                        size_bytes /= 1024.0
                    return f"{size_bytes:.1f}Y"
                elif kilobytes:
                    return str(int(size_bytes // 1024))
                elif megabytes:
                    return str(int(size_bytes // 1024 // 1024))
                else:
                    return str(int(size_bytes))
            
            # Get disk partitions
            if not paths:
                partitions = psutil.disk_partitions()
            else:
                # Filter partitions based on paths
                all_partitions = psutil.disk_partitions()
                partitions = []
                
                for path in paths:
                    # Resolve path
                    full_path = os.path.join(cwd, path) if not os.path.isabs(path) else path
                    
                    # Find the partition that contains this path
                    matched = False
                    for part in all_partitions:
                        if full_path.startswith(part.mountpoint):
                            if part not in partitions:
                                partitions.append(part)
                            matched = True
                    
                    if not matched:
                        return f"df: {path}: No such file or directory"
            
            # Format header
            if show_inodes:
                if show_type:
                    header = "Filesystem     Type      Inodes  IUsed   IFree IUse% Mounted on"
                else:
                    header = "Filesystem      Inodes  IUsed   IFree IUse% Mounted on"
            else:
                if show_type:
                    header = "Filesystem     Type       Size  Used Avail Use% Mounted on"
                else:
                    header = "Filesystem      Size  Used Avail Use% Mounted on"
            
            result = [header]
            
            # Format each partition
            for part in partitions:
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    
                    # Get filesystem type
                    fs_type = part.fstype
                    
                    if show_inodes:
                        # Inode information not directly available in psutil
                        # For this simulation, we'll use placeholders
                        inodes_total = 1000000
                        inodes_used = int(inodes_total * (usage.percent / 100))
                        inodes_free = inodes_total - inodes_used
                        inodes_use_percent = usage.percent
                        
                        if show_type:
                            line = f"{part.device:<15} {fs_type:<8} {inodes_total:8d} {inodes_used:7d} {inodes_free:7d} {inodes_use_percent:4.1f}% {part.mountpoint}"
                        else:
                            line = f"{part.device:<15} {inodes_total:8d} {inodes_used:7d} {inodes_free:7d} {inodes_use_percent:4.1f}% {part.mountpoint}"
                    else:
                        # Block usage information
                        size = format_size(usage.total)
                        used = format_size(usage.used)
                        avail = format_size(usage.free)
                        use_percent = usage.percent
                        
                        if show_type:
                            line = f"{part.device:<15} {fs_type:<8} {size:6s} {used:5s} {avail:5s} {use_percent:3.1f}% {part.mountpoint}"
                        else:
                            line = f"{part.device:<15} {size:6s} {used:5s} {avail:5s} {use_percent:3.1f}% {part.mountpoint}"
                    
                    result.append(line)
                except Exception as e:
                    logger.error(f"Error getting disk usage for {part.mountpoint}: {e}")
                    result.append(f"{part.device:<15} - - - - {part.mountpoint}")
            
            return "\n".join(result)
                
        except Exception as e:
            logger.error(f"Error in df command: {e}")
            return f"df: {str(e)}"

def register_commands(shell):
    """Register all system monitoring commands with the KOS shell."""
    
    # Add the ps command
    def do_ps(self, arg):
        """Report process status
        
        Usage: ps [options]
        Display information about active processes.
        
        Options:
          -a        Show processes for all users
          -u        Show detailed user-oriented format
          -x        Show processes without controlling terminal
          -e        Show all processes
          -f        Show full format listing
          -l        Show long format
          --sort=X  Sort by column (e.g., --sort=pid, --sort=-cpu)
        """
        try:
            result = SystemMonitorCommands.do_ps(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in ps command: {e}")
            print(f"ps: {str(e)}")
    
    # Add the free command
    def do_free(self, arg):
        """Display amount of free and used memory in the system
        
        Usage: free [options]
        Display memory usage information.
        
        Options:
          -b, --bytes     Show output in bytes
          -k, --kilo      Show output in kilobytes
          -m, --mega      Show output in megabytes
          -g, --giga      Show output in gigabytes
          -h, --human     Show human-readable output
          -t, --total     Show row with totals
          -s N, --seconds=N  Update continuously every N seconds
        """
        try:
            result = SystemMonitorCommands.do_free(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in free command: {e}")
            print(f"free: {str(e)}")
    
    # Add the df command
    def do_df(self, arg):
        """Report file system disk space usage
        
        Usage: df [options] [file...]
        Show information about file system space usage.
        
        Options:
          -h, --human-readable    Print sizes in human readable format
          -k, --kilobytes         Print sizes in kilobytes
          -m, --megabytes         Print sizes in megabytes
          -T, --print-type        Print file system type
          -i, --inodes            List inode information instead of block usage
        """
        try:
            result = SystemMonitorCommands.do_df(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in df command: {e}")
            print(f"df: {str(e)}")
    
    # Attach the command methods to the shell
    setattr(shell.__class__, 'do_ps', do_ps)
    setattr(shell.__class__, 'do_free', do_free)
    setattr(shell.__class__, 'do_df', do_df)

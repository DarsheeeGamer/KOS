"""
Process Management Utilities for KOS Shell

This module implements Linux-style process management commands for the KOS shell,
providing utilities for process listing, monitoring, and control.
"""

import os
import re
import shlex
import logging
import time
import datetime
import subprocess
import signal
import psutil
from typing import List, Dict, Any, Optional, Tuple, Union

logger = logging.getLogger('KOS.shell.proc_utils')

class ProcessUtils:
    """Implementation of Linux-style process management utilities for KOS shell."""
    
    @staticmethod
    def do_ps(fs, cwd, arg):
        """Report process status
        
        Usage: ps [options]
        
        Options:
          -e, --everyone     Display all processes
          -f, --full         Full listing
          -l, --long         Long listing
          -a, --all          Show processes from all users
          -u USER            Show processes for specified user
          -p PID             Show process with specified PID
          
        Examples:
          ps
          ps -ef
          ps -u username
          ps -p 1234
        """
        args = shlex.split(arg)
        
        # Parse options
        show_all = False
        full_listing = False
        long_listing = False
        show_user = None
        show_pid = None
        
        # Extract options
        for i, arg in enumerate(args):
            if arg in ['-e', '--everyone']:
                show_all = True
            elif arg in ['-f', '--full']:
                full_listing = True
            elif arg in ['-l', '--long']:
                long_listing = True
            elif arg in ['-a', '--all']:
                show_all = True
            elif arg in ['-u'] and i + 1 < len(args):
                show_user = args[i + 1]
            elif arg.startswith('-u'):
                show_user = arg[2:]
            elif arg in ['-p'] and i + 1 < len(args):
                try:
                    show_pid = int(args[i + 1])
                except ValueError:
                    return f"Invalid PID: {args[i + 1]}"
            elif arg.startswith('-p'):
                try:
                    show_pid = int(arg[2:])
                except ValueError:
                    return f"Invalid PID: {arg[2:]}"
        
        # Check if psutil is available
        if not hasattr(psutil, 'process_iter'):
            return "Error: psutil module not available. Cannot list processes."
        
        # Get process list
        processes = []
        
        try:
            if show_pid:
                # Show only the specified process
                try:
                    proc = psutil.Process(show_pid)
                    processes.append(proc)
                except psutil.NoSuchProcess:
                    return f"Process with PID {show_pid} not found"
            else:
                # Get all processes
                for proc in psutil.process_iter(['pid', 'name', 'username', 'cmdline', 'status', 'cpu_percent', 'memory_percent']):
                    try:
                        # Filter by user if specified
                        if show_user and proc.info['username'] != show_user:
                            continue
                        
                        # Add to list
                        processes.append(proc)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
        except Exception as e:
            logger.error(f"Error getting process list: {e}")
            return f"Error getting process list: {str(e)}"
        
        # Format output
        if full_listing or long_listing:
            if full_listing:
                header = "UID        PID  PPID  C    STIME TTY          TIME CMD"
                result = [header]
                
                for proc in processes:
                    try:
                        # Get process info
                        pid = proc.pid
                        ppid = proc.ppid()
                        cpu_percent = proc.cpu_percent(interval=0.1)
                        create_time = datetime.datetime.fromtimestamp(proc.create_time()).strftime("%H:%M")
                        username = proc.username()
                        cmdline = " ".join(proc.cmdline()) if proc.cmdline() else proc.name()
                        
                        # Get terminal (simplified)
                        tty = "?"
                        
                        # Get CPU time
                        cpu_time = proc.cpu_times()
                        time_str = f"{int(cpu_time.user + cpu_time.system)}:{int((cpu_time.user + cpu_time.system) % 1 * 60):02d}"
                        
                        # Format line
                        result.append(f"{username:<10} {pid:5d} {ppid:5d} {int(cpu_percent):3d} {create_time:>7} {tty:<6} {time_str:>8} {cmdline}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            else:  # long_listing
                header = "F S   UID   PID  PPID  C PRI  NI ADDR SZ WCHAN  TTY          TIME CMD"
                result = [header]
                
                for proc in processes:
                    try:
                        # Get process info
                        pid = proc.pid
                        ppid = proc.ppid()
                        status = proc.status()[0]  # First letter of status (R, S, D, Z, etc.)
                        cpu_percent = proc.cpu_percent(interval=0.1)
                        username = proc.username()
                        cmdline = " ".join(proc.cmdline()) if proc.cmdline() else proc.name()
                        
                        # Get terminal (simplified)
                        tty = "?"
                        
                        # Get CPU time
                        cpu_time = proc.cpu_times()
                        time_str = f"{int(cpu_time.user + cpu_time.system)}:{int((cpu_time.user + cpu_time.system) % 1 * 60):02d}"
                        
                        # Get nice value
                        try:
                            nice = proc.nice()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            nice = 0
                        
                        # Get memory info
                        try:
                            mem_info = proc.memory_info()
                            size = mem_info.rss // 1024  # Size in KB
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            size = 0
                        
                        # Format line (simplified for cross-platform)
                        result.append(f"0 {status} {username:6} {pid:5d} {ppid:5d} {int(cpu_percent):1d}  20 {nice:3d}    - {size:6d}    - {tty:<6} {time_str:>8} {cmdline}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
        else:
            # Simple listing
            header = "  PID TTY          TIME CMD"
            result = [header]
            
            for proc in processes:
                try:
                    # Get process info
                    pid = proc.pid
                    cmdline = " ".join(proc.cmdline()) if proc.cmdline() else proc.name()
                    
                    # Get terminal (simplified)
                    tty = "?"
                    
                    # Get CPU time
                    cpu_time = proc.cpu_times()
                    time_str = f"{int(cpu_time.user + cpu_time.system)}:{int((cpu_time.user + cpu_time.system) % 1 * 60):02d}"
                    
                    # Format line
                    result.append(f"{pid:5d} {tty:<6} {time_str:>8} {cmdline}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        
        if len(result) == 1:
            return "No processes found"
        
        return "\n".join(result)
    
    @staticmethod
    def do_top(fs, cwd, arg):
        """Display Linux processes
        
        Usage: top [options]
        
        Options:
          -n NUM       Number of iterations to show before exiting
          -d SECONDS   Delay between updates
          -p PID       Monitor only process with specified PID
          
        Press 'q' to quit interactive display.
        
        Examples:
          top
          top -n 5
          top -d 2
          top -p 1234
        """
        args = shlex.split(arg)
        
        # Parse options
        iterations = None
        delay = 3.0  # Default delay
        monitor_pid = None
        
        i = 0
        while i < len(args):
            if args[i] == '-n' and i + 1 < len(args):
                try:
                    iterations = int(args[i + 1])
                    i += 2
                except ValueError:
                    return f"Invalid number of iterations: {args[i + 1]}"
            elif args[i] == '-d' and i + 1 < len(args):
                try:
                    delay = float(args[i + 1])
                    i += 2
                except ValueError:
                    return f"Invalid delay: {args[i + 1]}"
            elif args[i] == '-p' and i + 1 < len(args):
                try:
                    monitor_pid = int(args[i + 1])
                    i += 2
                except ValueError:
                    return f"Invalid PID: {args[i + 1]}"
            else:
                i += 1
        
        # Check if psutil is available
        if not hasattr(psutil, 'process_iter'):
            return "Error: psutil module not available. Cannot monitor processes."
        
        # For non-interactive mode, generate a snapshot
        if iterations is not None and iterations > 0:
            result = []
            
            for i in range(iterations):
                if i > 0:
                    time.sleep(delay)
                
                snapshot = ProcessUtils._generate_top_snapshot(monitor_pid)
                result.append(snapshot)
                result.append("\n" + "-" * 80 + "\n")
            
            return "\n".join(result)
        else:
            # Interactive mode not supported in this environment
            # Just show a single snapshot
            return ProcessUtils._generate_top_snapshot(monitor_pid)
    
    @staticmethod
    def _generate_top_snapshot(monitor_pid=None):
        """Generate a snapshot of system stats for top command"""
        # Get system info
        uptime = time.time() - psutil.boot_time()
        uptime_str = f"{int(uptime // 3600)}:{int((uptime % 3600) // 60):02d}"
        
        load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else (0.0, 0.0, 0.0)
        
        # Get CPU and memory info
        cpu_percent = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        # Format header
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        header = [
            f"top - {current_time} up {uptime_str}, load average: {load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}",
            f"Tasks: {len(list(psutil.process_iter()))} total",
            f"CPU usage: {cpu_percent:.1f}% user, {100.0 - cpu_percent:.1f}% system",
            f"Mem: {mem.total // 1024 // 1024}M total, {mem.used // 1024 // 1024}M used, {mem.free // 1024 // 1024}M free, {mem.cached // 1024 // 1024}M cached",
            f"Swap: {swap.total // 1024 // 1024}M total, {swap.used // 1024 // 1024}M used, {swap.free // 1024 // 1024}M free"
        ]
        
        # Format process list
        process_header = "  PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND"
        processes = []
        
        # Get process list
        try:
            process_list = []
            
            for proc in psutil.process_iter(['pid', 'name', 'username', 'cmdline', 'status', 'cpu_percent', 'memory_percent']):
                try:
                    # Filter by PID if specified
                    if monitor_pid and proc.pid != monitor_pid:
                        continue
                    
                    # Update CPU percent
                    proc.cpu_percent(interval=None)
                    
                    # Add to list
                    process_list.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Wait for CPU stats to be collected
            time.sleep(0.1)
            
            # Get process info and sort by CPU usage
            for proc in process_list:
                try:
                    pid = proc.pid
                    cpu_percent = proc.cpu_percent(interval=None)
                    memory_percent = proc.memory_percent()
                    
                    # Skip processes with 0% CPU if too many processes
                    if len(process_list) > 20 and cpu_percent < 0.1:
                        continue
                    
                    username = proc.username()
                    cmdline = " ".join(proc.cmdline()) if proc.cmdline() else proc.name()
                    
                    # Get memory info
                    mem_info = proc.memory_info()
                    virt = mem_info.vms // 1024  # KB
                    res = mem_info.rss // 1024   # KB
                    shr = getattr(mem_info, 'shared', 0) // 1024  # KB
                    
                    # Get process status
                    status = proc.status()[0]  # First letter of status
                    
                    # Get nice value
                    nice = proc.nice()
                    
                    # Get CPU time
                    cpu_time = proc.cpu_times()
                    cputime = cpu_time.user + cpu_time.system
                    cputime_str = f"{int(cputime // 60)}:{int(cputime % 60):02d}.{int((cputime * 100) % 100):02d}"
                    
                    # Format line
                    processes.append((cpu_percent, f"{pid:5d} {username:8s} {20:3d} {nice:3d} {virt:7d} {res:6d} {shr:6d} {status} {cpu_percent:5.1f} {memory_percent:5.1f} {cputime_str:9s} {cmdline}"))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception as e:
            logger.error(f"Error getting process info: {e}")
            processes.append((0.0, f"Error getting process info: {str(e)}"))
        
        # Sort by CPU usage
        processes.sort(key=lambda x: x[0], reverse=True)
        
        # Limit to top processes
        processes = processes[:20]
        
        # Format result
        result = header + ["", process_header] + [p[1] for p in processes]
        
        return "\n".join(result)
    
    @staticmethod
    def do_kill(fs, cwd, arg):
        """Terminate processes
        
        Usage: kill [options] PID...
        
        Options:
          -s SIGNAL, --signal=SIGNAL   Specify the signal to send
          -l, --list                   List signal names
          
        Examples:
          kill 1234
          kill -s TERM 1234
          kill -9 1234 5678
          kill -l
        """
        args = shlex.split(arg)
        
        # List signals if requested
        if len(args) == 1 and args[0] in ['-l', '--list']:
            signals = []
            for sig_name in dir(signal):
                if sig_name.startswith('SIG') and not sig_name.startswith('SIG_'):
                    signals.append(sig_name)
            signals.sort()
            return " ".join(signals)
        
        # Parse options
        signal_name = 'SIGTERM'  # Default signal
        pids = []
        
        i = 0
        while i < len(args):
            if args[i] in ['-s', '--signal'] and i + 1 < len(args):
                signal_name = args[i + 1]
                i += 2
            elif args[i].startswith('--signal='):
                signal_name = args[i][9:]
                i += 1
            elif args[i].startswith('-') and args[i][1:].isdigit():
                signal_name = f"SIG{args[i][1:]}"
                i += 1
            else:
                try:
                    pids.append(int(args[i]))
                    i += 1
                except ValueError:
                    return f"Invalid PID: {args[i]}"
        
        if not pids:
            return "No PIDs specified"
        
        # Get signal number
        sig_num = None
        
        try:
            # Try direct signal number
            if signal_name.isdigit():
                sig_num = int(signal_name)
            # Try SIG prefix
            elif hasattr(signal, signal_name):
                sig_num = getattr(signal, signal_name)
            # Try without SIG prefix
            elif hasattr(signal, f"SIG{signal_name}"):
                sig_num = getattr(signal, f"SIG{signal_name}")
            else:
                return f"Unknown signal: {signal_name}"
        except (AttributeError, ValueError):
            return f"Invalid signal: {signal_name}"
        
        # Send signal to each process
        result = []
        
        for pid in pids:
            try:
                proc = psutil.Process(pid)
                proc.send_signal(sig_num)
                result.append(f"Sent signal {signal_name} to process {pid}")
            except psutil.NoSuchProcess:
                result.append(f"Process {pid} does not exist")
            except psutil.AccessDenied:
                result.append(f"Permission denied for process {pid}")
            except Exception as e:
                result.append(f"Error sending signal to process {pid}: {e}")
        
        return "\n".join(result)
    
    @staticmethod
    def do_nice(fs, cwd, arg):
        """Run a program with modified scheduling priority
        
        Usage: nice [options] COMMAND [ARG]...
        
        Options:
          -n ADJUSTMENT, --adjustment=ADJUSTMENT
                            Add ADJUSTMENT to the nice value (default: 10)
                            
        Examples:
          nice -n 5 command arg1 arg2
          nice --adjustment=10 command
        """
        args = shlex.split(arg)
        
        # Parse options
        adjustment = 10  # Default adjustment
        command_args = []
        
        i = 0
        while i < len(args):
            if args[i] in ['-n', '--adjustment'] and i + 1 < len(args):
                try:
                    adjustment = int(args[i + 1])
                    i += 2
                except ValueError:
                    return f"Invalid adjustment: {args[i + 1]}"
            elif args[i].startswith('--adjustment='):
                try:
                    adjustment = int(args[i][13:])
                    i += 1
                except ValueError:
                    return f"Invalid adjustment: {args[i][13:]}"
            else:
                command_args = args[i:]
                break
        
        if not command_args:
            return "No command specified"
        
        # Check if psutil is available
        if not hasattr(psutil, 'Process'):
            return "Error: psutil module not available. Cannot adjust process priority."
        
        try:
            # Get current process priority
            current_nice = os.nice(0)
            
            # Calculate new nice value
            new_nice = current_nice + adjustment
            
            # Limit to valid range
            new_nice = max(-20, min(19, new_nice))
            
            # Start the process with adjusted priority
            proc = subprocess.Popen(command_args, preexec_fn=lambda: os.nice(new_nice))
            
            return f"Started process {proc.pid} with nice value {new_nice}"
        except Exception as e:
            return f"Error: {str(e)}"
    
    @staticmethod
    def do_pgrep(fs, cwd, arg):
        """Look up processes by name, pattern, or other attributes
        
        Usage: pgrep [options] PATTERN
        
        Options:
          -f, --full         Match against full command line
          -l, --list-name    List the process name as well as the PID
          -u, --user USER    Only match processes whose user is USER
          -x, --exact        Only match processes whose names exactly match PATTERN
          
        Examples:
          pgrep python
          pgrep -l nginx
          pgrep -f "python script.py"
          pgrep -u username pattern
        """
        args = shlex.split(arg)
        
        # Parse options
        full_match = False
        list_name = False
        user = None
        exact_match = False
        pattern = None
        
        i = 0
        while i < len(args):
            if args[i] in ['-f', '--full']:
                full_match = True
                i += 1
            elif args[i] in ['-l', '--list-name']:
                list_name = True
                i += 1
            elif args[i] in ['-u', '--user'] and i + 1 < len(args):
                user = args[i + 1]
                i += 2
            elif args[i].startswith('--user='):
                user = args[i][7:]
                i += 1
            elif args[i] in ['-x', '--exact']:
                exact_match = True
                i += 1
            else:
                pattern = args[i]
                i += 1
        
        if not pattern:
            return "No pattern specified"
        
        # Check if psutil is available
        if not hasattr(psutil, 'process_iter'):
            return "Error: psutil module not available. Cannot search processes."
        
        # Compile regex
        try:
            if exact_match:
                regex = re.compile(f"^{pattern}$")
            else:
                regex = re.compile(pattern)
        except re.error as e:
            return f"Invalid regular expression: {e}"
        
        # Search processes
        results = []
        
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cmdline']):
            try:
                # Filter by user if specified
                if user and proc.info['username'] != user:
                    continue
                
                # Get process info
                name = proc.info['name']
                cmdline = " ".join(proc.info['cmdline']) if proc.info['cmdline'] else name
                
                # Match against pattern
                if full_match:
                    if regex.search(cmdline):
                        if list_name:
                            results.append(f"{proc.info['pid']} {name}")
                        else:
                            results.append(f"{proc.info['pid']}")
                else:
                    if regex.search(name):
                        if list_name:
                            results.append(f"{proc.info['pid']} {name}")
                        else:
                            results.append(f"{proc.info['pid']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if not results:
            return "No matching processes found"
        
        return "\n".join(results)

def register_commands(shell):
    """Register all process utility commands with the KOS shell."""
    
    # Register the ps command
    def do_ps(self, arg):
        """Report process status"""
        try:
            result = ProcessUtils.do_ps(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in ps command: {e}")
            print(f"ps: {str(e)}")
    
    # Register the top command
    def do_top(self, arg):
        """Display Linux processes"""
        try:
            result = ProcessUtils.do_top(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in top command: {e}")
            print(f"top: {str(e)}")
    
    # Register the kill command
    def do_kill(self, arg):
        """Terminate processes"""
        try:
            result = ProcessUtils.do_kill(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in kill command: {e}")
            print(f"kill: {str(e)}")
    
    # Register the nice command
    def do_nice(self, arg):
        """Run a program with modified scheduling priority"""
        try:
            result = ProcessUtils.do_nice(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in nice command: {e}")
            print(f"nice: {str(e)}")
    
    # Register the pgrep command
    def do_pgrep(self, arg):
        """Look up processes by name, pattern, or other attributes"""
        try:
            result = ProcessUtils.do_pgrep(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in pgrep command: {e}")
            print(f"pgrep: {str(e)}")
    
    # Attach the command methods to the shell
    setattr(shell.__class__, 'do_ps', do_ps)
    setattr(shell.__class__, 'do_top', do_top)
    setattr(shell.__class__, 'do_kill', do_kill)
    setattr(shell.__class__, 'do_nice', do_nice)
    setattr(shell.__class__, 'do_pgrep', do_pgrep)

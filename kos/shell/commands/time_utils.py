"""
Time Command Implementation for KOS
===================================

Provides Unix-like time command functionality:
- Command execution timing
- Resource usage measurement
- Multiple output formats
- Process monitoring
"""

import os
import sys
import time
import subprocess
import resource
import signal
import threading
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

@dataclass
class TimeStats:
    """Time and resource usage statistics"""
    # Time measurements
    real_time: float = 0.0      # Wall clock time
    user_time: float = 0.0      # User CPU time
    sys_time: float = 0.0       # System CPU time
    
    # Memory usage
    max_memory_kb: int = 0      # Maximum resident set size
    avg_memory_kb: int = 0      # Average memory usage
    
    # I/O statistics
    major_page_faults: int = 0  # Page faults requiring I/O
    minor_page_faults: int = 0  # Page faults not requiring I/O
    voluntary_switches: int = 0  # Voluntary context switches
    involuntary_switches: int = 0 # Involuntary context switches
    
    # File system
    fs_inputs: int = 0          # File system inputs
    fs_outputs: int = 0         # File system outputs
    
    # Exit status
    exit_code: int = 0
    exit_signal: Optional[int] = None
    
    # Command info
    command: str = ""
    pid: int = 0

class TimeFormat(Enum):
    """Time output formats"""
    DEFAULT = "default"
    VERBOSE = "verbose"
    POSIX = "posix"
    GNU = "gnu"
    CUSTOM = "custom"

class TimeCommand:
    """Implementation of Unix time command"""
    
    def __init__(self):
        self.format_string = None
        self.output_file = None
        self.append_mode = False
        self.verbose = False
        self.format_type = TimeFormat.DEFAULT
        
    def execute(self, args: List[str]) -> Tuple[int, str, str]:
        """Execute time command with given arguments"""
        if not args:
            return 1, "", "time: missing command\nUsage: time [options] command [args...]"
        
        # Parse time command options
        parsed_args, command_args = self._parse_args(args)
        
        if not command_args:
            return 1, "", "time: missing command to time"
        
        # Execute the command and measure time/resources
        stats = self._time_command(command_args)
        
        # Format output
        output = self._format_output(stats)
        
        # Write to file if specified
        if self.output_file:
            try:
                mode = 'a' if self.append_mode else 'w'
                with open(self.output_file, mode) as f:
                    f.write(output + '\n')
            except IOError as e:
                return 1, "", f"time: cannot write to {self.output_file}: {e}"
        
        # Return command's exit code and timing info
        return stats.exit_code, "", output
    
    def _parse_args(self, args: List[str]) -> Tuple[Dict[str, Any], List[str]]:
        """Parse time command arguments"""
        parsed = {}
        command_args = []
        i = 0
        
        while i < len(args):
            arg = args[i]
            
            if arg == "-v" or arg == "--verbose":
                self.verbose = True
                self.format_type = TimeFormat.VERBOSE
            elif arg == "-p" or arg == "--portability":
                self.format_type = TimeFormat.POSIX
            elif arg == "-f" or arg == "--format":
                if i + 1 >= len(args):
                    raise ValueError("option requires an argument -- f")
                i += 1
                self.format_string = args[i]
                self.format_type = TimeFormat.CUSTOM
            elif arg == "-o" or arg == "--output":
                if i + 1 >= len(args):
                    raise ValueError("option requires an argument -- o")
                i += 1
                self.output_file = args[i]
            elif arg == "-a" or arg == "--append":
                self.append_mode = True
            elif arg == "--help":
                return parsed, []  # Will show help
            elif arg.startswith("-"):
                raise ValueError(f"unknown option: {arg}")
            else:
                # Rest are command arguments
                command_args = args[i:]
                break
            
            i += 1
        
        return parsed, command_args
    
    def _time_command(self, command_args: List[str]) -> TimeStats:
        """Execute command and collect timing/resource statistics"""
        stats = TimeStats()
        stats.command = " ".join(command_args)
        
        # Record start time and resources
        start_time = time.time()
        start_resources = resource.getrusage(resource.RUSAGE_CHILDREN)
        
        try:
            # Execute the command
            process = subprocess.Popen(
                command_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid  # Create new process group
            )
            
            stats.pid = process.pid
            
            # Monitor memory usage in background
            memory_monitor = MemoryMonitor(process.pid)
            memory_thread = threading.Thread(target=memory_monitor.monitor, daemon=True)
            memory_thread.start()
            
            # Wait for process completion
            stdout, stderr = process.communicate()
            
            # Stop memory monitoring
            memory_monitor.stop()
            memory_thread.join(timeout=1.0)
            
            # Record end time and resources
            end_time = time.time()
            end_resources = resource.getrusage(resource.RUSAGE_CHILDREN)
            
            # Calculate statistics
            stats.real_time = end_time - start_time
            stats.user_time = end_resources.ru_utime - start_resources.ru_utime
            stats.sys_time = end_resources.ru_stime - start_resources.ru_stime
            
            # Resource usage differences
            stats.max_memory_kb = max(end_resources.ru_maxrss - start_resources.ru_maxrss, 0)
            stats.major_page_faults = end_resources.ru_majflt - start_resources.ru_majflt
            stats.minor_page_faults = end_resources.ru_minflt - start_resources.ru_minflt
            stats.voluntary_switches = end_resources.ru_nvcsw - start_resources.ru_nvcsw
            stats.involuntary_switches = end_resources.ru_nivcsw - start_resources.ru_nivcsw
            stats.fs_inputs = end_resources.ru_inblock - start_resources.ru_inblock
            stats.fs_outputs = end_resources.ru_oublock - start_resources.ru_oublock
            
            # Memory statistics from monitor
            if memory_monitor.max_memory_kb > 0:
                stats.max_memory_kb = memory_monitor.max_memory_kb
                stats.avg_memory_kb = memory_monitor.avg_memory_kb
            
            stats.exit_code = process.returncode
            
            # Print command output
            if stdout:
                print(stdout.decode('utf-8'), end='')
            if stderr:
                print(stderr.decode('utf-8'), end='', file=sys.stderr)
                
        except KeyboardInterrupt:
            # Handle Ctrl+C
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                process.wait(timeout=5)
            except:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            
            stats.exit_code = 130  # Interrupted
            stats.exit_signal = signal.SIGINT
            
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            stats.exit_code = 124  # Timeout
            
        except Exception as e:
            stats.exit_code = 1
            print(f"time: {e}", file=sys.stderr)
        
        return stats
    
    def _format_output(self, stats: TimeStats) -> str:
        """Format timing output according to selected format"""
        if self.format_type == TimeFormat.POSIX:
            return self._format_posix(stats)
        elif self.format_type == TimeFormat.VERBOSE:
            return self._format_verbose(stats)
        elif self.format_type == TimeFormat.CUSTOM and self.format_string:
            return self._format_custom(stats)
        else:
            return self._format_default(stats)
    
    def _format_default(self, stats: TimeStats) -> str:
        """Default time format (bash-like)"""
        return f"""
real\t{self._format_time(stats.real_time)}
user\t{self._format_time(stats.user_time)}
sys\t{self._format_time(stats.sys_time)}"""
    
    def _format_posix(self, stats: TimeStats) -> str:
        """POSIX-compliant format"""
        return f"""real {stats.real_time:.2f}
user {stats.user_time:.2f}
sys {stats.sys_time:.2f}"""
    
    def _format_verbose(self, stats: TimeStats) -> str:
        """Verbose GNU time format"""
        cpu_percent = 0.0
        if stats.real_time > 0:
            cpu_percent = ((stats.user_time + stats.sys_time) / stats.real_time) * 100
        
        return f"""	Command being timed: "{stats.command}"
	User time (seconds): {stats.user_time:.2f}
	System time (seconds): {stats.sys_time:.2f}
	Percent of CPU this job got: {cpu_percent:.0f}%
	Elapsed (wall clock) time (h:mm:ss or m:ss): {self._format_time(stats.real_time)}
	Average shared text size (kbytes): 0
	Average unshared data size (kbytes): 0
	Average stack size (kbytes): 0
	Average total size (kbytes): 0
	Maximum resident set size (kbytes): {stats.max_memory_kb}
	Average resident set size (kbytes): {stats.avg_memory_kb}
	Major (requiring I/O) page faults: {stats.major_page_faults}
	Minor (reclaiming a frame) page faults: {stats.minor_page_faults}
	Voluntary context switches: {stats.voluntary_switches}
	Involuntary context switches: {stats.involuntary_switches}
	Swaps: 0
	File system inputs: {stats.fs_inputs}
	File system outputs: {stats.fs_outputs}
	Socket messages sent: 0
	Socket messages received: 0
	Signals delivered: 0
	Page size (bytes): {resource.getpagesize()}
	Exit status: {stats.exit_code}"""
    
    def _format_custom(self, stats: TimeStats) -> str:
        """Custom format string"""
        # GNU time format specifiers
        format_map = {
            '%E': self._format_time(stats.real_time),
            '%e': f"{stats.real_time:.2f}",
            '%U': f"{stats.user_time:.2f}",
            '%S': f"{stats.sys_time:.2f}",
            '%P': f"{((stats.user_time + stats.sys_time) / max(stats.real_time, 0.01)) * 100:.0f}%",
            '%M': str(stats.max_memory_kb),
            '%t': str(stats.avg_memory_kb),
            '%K': str(stats.max_memory_kb + stats.avg_memory_kb),
            '%D': str(stats.avg_memory_kb),
            '%p': str(stats.avg_memory_kb),
            '%X': str(0),  # Average shared text size
            '%Z': str(resource.getpagesize()),
            '%F': str(stats.major_page_faults),
            '%R': str(stats.minor_page_faults),
            '%W': str(0),  # Swaps
            '%c': str(stats.involuntary_switches),
            '%w': str(stats.voluntary_switches),
            '%I': str(stats.fs_inputs),
            '%O': str(stats.fs_outputs),
            '%r': str(0),  # Socket messages received
            '%s': str(0),  # Socket messages sent
            '%k': str(0),  # Signals delivered
            '%x': str(stats.exit_code),
            '%C': stats.command,
            '%%': '%',
            '\\n': '\n',
            '\\t': '\t',
        }
        
        result = self.format_string
        for spec, value in format_map.items():
            result = result.replace(spec, value)
        
        return result
    
    def _format_time(self, seconds: float) -> str:
        """Format time in h:mm:ss.ss or m:ss.ss format"""
        if seconds < 0:
            return "0:00.00"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:05.2f}"
        else:
            return f"{minutes}:{secs:05.2f}"

class MemoryMonitor:
    """Monitor memory usage of a process"""
    
    def __init__(self, pid: int):
        self.pid = pid
        self.max_memory_kb = 0
        self.total_memory_kb = 0
        self.sample_count = 0
        self.running = True
        
    def monitor(self):
        """Monitor memory usage"""
        while self.running:
            try:
                # Read memory usage from /proc/pid/status
                with open(f"/proc/{self.pid}/status", 'r') as f:
                    for line in f:
                        if line.startswith('VmRSS:'):
                            # Extract memory in kB
                            memory_kb = int(line.split()[1])
                            self.max_memory_kb = max(self.max_memory_kb, memory_kb)
                            self.total_memory_kb += memory_kb
                            self.sample_count += 1
                            break
                
                time.sleep(0.1)  # Sample every 100ms
                
            except (FileNotFoundError, ProcessLookupError, ValueError):
                # Process finished or not found
                break
            except Exception:
                # Other errors, continue monitoring
                time.sleep(0.1)
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
    
    @property
    def avg_memory_kb(self) -> int:
        """Average memory usage"""
        if self.sample_count > 0:
            return self.total_memory_kb // self.sample_count
        return 0

# Shell command integration
def register_time_commands(shell):
    """Register time-related commands with the shell"""
    
    def time_command(args):
        """time command implementation"""
        if not args:
            return """Usage: time [options] command [args...]
Time the execution of a command and report resource usage.

Options:
  -v, --verbose         Use verbose output format
  -p, --portability     Use POSIX format
  -f, --format=FORMAT   Use custom format string
  -o, --output=FILE     Write output to FILE
  -a, --append          Append to output file
  --help                Show this help message

Format specifiers for -f option:
  %E    Elapsed real time (h:mm:ss)
  %e    Elapsed real time (seconds)
  %U    User CPU time (seconds)
  %S    System CPU time (seconds)
  %P    Percentage of CPU
  %M    Maximum resident set size (KB)
  %C    Command line
  %x    Exit status

Examples:
  time ls -la
  time -v grep pattern file.txt
  time -f "%E elapsed, %U user, %S system" make
"""
        
        try:
            time_cmd = TimeCommand()
            return_code, stdout, stderr = time_cmd.execute(args)
            
            if stdout:
                print(stdout, end='')
            if stderr:
                print(stderr, file=sys.stderr)
            
            return return_code == 0
            
        except Exception as e:
            print(f"time: {e}", file=sys.stderr)
            return False
    
    def times_command(args):
        """times command - show accumulated user and system times"""
        if args and args[0] in ['-h', '--help']:
            return """Usage: times
Display accumulated user and system times for the shell and its children.

Output format:
  user_time system_time child_user_time child_system_time
"""
        
        try:
            # Get resource usage for current process
            self_usage = resource.getrusage(resource.RUSAGE_SELF)
            children_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
            
            print(f"{self_usage.ru_utime:.2f} {self_usage.ru_stime:.2f} "
                  f"{children_usage.ru_utime:.2f} {children_usage.ru_stime:.2f}")
            
            return True
            
        except Exception as e:
            print(f"times: {e}", file=sys.stderr)
            return False
    
    def uptime_command(args):
        """uptime command - show system uptime and load"""
        if args and args[0] in ['-h', '--help']:
            return """Usage: uptime [options]
Show system uptime and load averages.

Options:
  -p, --pretty    Show uptime in pretty format
  -s, --since     Show time when system started
  -h, --help      Show this help message
"""
        
        try:
            pretty = '-p' in args or '--pretty' in args
            since = '-s' in args or '--since' in args
            
            # Read uptime from /proc/uptime
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.read().split()[0])
            
            # Read load averages
            with open('/proc/loadavg', 'r') as f:
                load_parts = f.read().split()
                load1, load5, load15 = load_parts[0], load_parts[1], load_parts[2]
            
            # Calculate uptime components
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            
            if since:
                # Show boot time
                boot_time = time.time() - uptime_seconds
                boot_date = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(boot_time))
                print(boot_date)
            elif pretty:
                # Pretty format
                if days > 0:
                    print(f"up {days} days, {hours} hours, {minutes} minutes")
                elif hours > 0:
                    print(f"up {hours} hours, {minutes} minutes")
                else:
                    print(f"up {minutes} minutes")
            else:
                # Standard format
                current_time = time.strftime('%H:%M:%S')
                users = 0  # Could be enhanced to count actual users
                
                if days > 0:
                    uptime_str = f"{days} days, {hours}:{minutes:02d}"
                else:
                    uptime_str = f"{hours}:{minutes:02d}"
                
                print(f" {current_time} up {uptime_str}, {users} users, "
                      f"load average: {load1}, {load5}, {load15}")
            
            return True
            
        except Exception as e:
            print(f"uptime: {e}", file=sys.stderr)
            return False
    
    def date_command(args):
        """date command - display or set system date"""
        if args and args[0] in ['-h', '--help']:
            return """Usage: date [options] [+format]
Display or set the system date.

Options:
  -u, --utc         Use UTC time
  -R, --rfc-2822    Output RFC 2822 format
  -I, --iso-8601    Output ISO 8601 format
  -r, --reference   Display last modification time of file
  -d, --date        Display specified date
  -s, --set         Set system date (requires privileges)
  -h, --help        Show this help message

Format specifiers:
  %Y    Year (4 digits)
  %y    Year (2 digits)
  %m    Month (01-12)
  %d    Day (01-31)
  %H    Hour (00-23)
  %M    Minute (00-59)
  %S    Second (00-59)
  %A    Full weekday name
  %a    Abbreviated weekday name
  %B    Full month name
  %b    Abbreviated month name

Examples:
  date
  date +%Y-%m-%d
  date -R
  date -u
"""
        
        try:
            utc = '-u' in args or '--utc' in args
            rfc2822 = '-R' in args or '--rfc-2822' in args
            iso8601 = '-I' in args or '--iso-8601' in args
            
            # Parse other options
            reference_file = None
            date_string = None
            set_date = None
            format_string = None
            
            i = 0
            while i < len(args):
                arg = args[i]
                if arg in ['-r', '--reference']:
                    if i + 1 < len(args):
                        reference_file = args[i + 1]
                        i += 1
                elif arg in ['-d', '--date']:
                    if i + 1 < len(args):
                        date_string = args[i + 1]
                        i += 1
                elif arg in ['-s', '--set']:
                    if i + 1 < len(args):
                        set_date = args[i + 1]
                        i += 1
                elif arg.startswith('+'):
                    format_string = arg[1:]
                i += 1
            
            # Determine time to display
            if reference_file:
                try:
                    timestamp = os.path.getmtime(reference_file)
                except OSError as e:
                    print(f"date: {reference_file}: {e}", file=sys.stderr)
                    return False
            elif date_string:
                # Parse date string (simplified)
                try:
                    import dateutil.parser
                    dt = dateutil.parser.parse(date_string)
                    timestamp = dt.timestamp()
                except (ImportError, ValueError) as e:
                    print(f"date: invalid date '{date_string}'", file=sys.stderr)
                    return False
            else:
                timestamp = time.time()
            
            # Set date if requested
            if set_date:
                print("date: setting system date requires root privileges", file=sys.stderr)
                return False
            
            # Format time
            if utc:
                time_struct = time.gmtime(timestamp)
            else:
                time_struct = time.localtime(timestamp)
            
            if format_string:
                output = time.strftime(format_string, time_struct)
            elif rfc2822:
                output = time.strftime('%a, %d %b %Y %H:%M:%S %z', time_struct)
            elif iso8601:
                output = time.strftime('%Y-%m-%dT%H:%M:%S%z', time_struct)
            else:
                output = time.strftime('%a %b %d %H:%M:%S %Z %Y', time_struct)
            
            print(output)
            return True
            
        except Exception as e:
            print(f"date: {e}", file=sys.stderr)
            return False
    
    # Register commands
    shell.register_command('time', time_command)
    shell.register_command('times', times_command)
    shell.register_command('uptime', uptime_command)
    shell.register_command('date', date_command)

__all__ = ['TimeCommand', 'TimeStats', 'MemoryMonitor', 'register_time_commands']
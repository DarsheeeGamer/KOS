"""
Enhanced shell implementation with advanced features and improved performance
"""
import cmd
import shlex
import os
import signal
import re
import logging
import sys
import time
import psutil  # Added import for system information
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from cachetools import TTLCache

try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
    from rich.panel import Panel
    from rich.syntax import Syntax
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = Table = Progress = SpinnerColumn = TimeElapsedColumn = Panel = Syntax = None
    logging.warning("Rich library not available, falling back to basic output")

from ..filesystem.base import FileSystem
from ..process.manager import ProcessManager
from ..package.manager import PackageManager
from ..exceptions import KOSError, FileSystemError, FileNotFound, NotADirectory, IsADirectory
from ..user_system import UserSystem
from .file_commands import touch_file, find_files, grep_text
from .pip_handler import PipCommandHandler
from .system_monitor import SystemMonitor
from .commands.nano import nano as nano_editor
from .commands.textproc import cut_command, paste_command, tr_command

logger = logging.getLogger('KOS.shell')


class KOSShell(cmd.Cmd):
    """Enhanced KOS shell with advanced features"""
    HISTORY_FILE = ".kos_history"
    MAX_HISTORY = 1000
    COMMAND_HELP_FILE = "command_help.json"

    def __init__(self, filesystem: FileSystem, package_manager: PackageManager,
                 process_manager: ProcessManager, user_system: UserSystem):
        super().__init__()
        self.fs = filesystem
        self.pm = package_manager
        self.process_mgr = process_manager
        self.us = user_system
        # Use custom history manager
        from .history_manager import get_history_manager
        self.history_manager = get_history_manager()
        self.history: List[str] = []
        self.console = Console() if RICH_AVAILABLE and Console else None
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._resource_cache = TTLCache(
            maxsize=100, ttl=1)  # Cache resource usage for 1 second
        self._load_history_from_manager()
        self._setup_signal_handlers()
        
        # Initialize package CLI integration
        self._init_package_cli_integration()

        # Enhanced command categories with descriptions
        self.command_categories = {
            "File Operations": {
                "ls": "List directory contents with enhanced formatting",
                "cd": "Change directory with path completion",
                "pwd": "Print working directory",
                "mkdir": "Create directory with permissions",
                "touch": "Create or update file timestamps",
                "cat": "Display file contents with syntax highlighting",
                "rm": "Remove files or directories",
                "cp": "Copy files or directories",
                "mv": "Move/rename files or directories",
                "chmod": "Change file permissions",
                "chown": "Change file ownership",
                "ln": "Create links",
                "grep": "Search file patterns with highlighting",
                "find": "Search files with advanced criteria",
                "tree": "Display directory structure",
                "nano": "Nano-like text editor for file editing"
            },
            "Process Management": {
                "ps": "Display process information",
                "top": "Interactive process viewer",
                "kill": "Send signals to processes",
                "nice": "Change process priority",
                "renice": "Adjust process priority",
                "pstree": "Show process hierarchy",
                "jobs": "List background jobs"
            },
            "System Operations": {
                "whoami": "Display current user",
                "hostname": "Show/set system hostname",
                "su": "Switch user",
                "useradd": "Add new user",
                "userdel": "Delete user",
                "passwd": "Change password",
                "groups": "Show user groups",
                "kudo": "Execute with elevated privileges",
                "clear": "Clear terminal screen",
                "users": "List logged-in users"
            },
            "Text Processing": {
                "sed": "Stream editor",
                "awk": "Pattern scanning/processing",
                "head": "Output first part of files",
                "tail": "Output last part of files",
                "wc": "Print word/line/byte counts",
                "sort": "Sort lines of text files",
                "uniq": "Report/omit repeated lines",
                "cut": "Remove sections from lines",
                "tr": "Translate/delete characters",
                "diff": "Compare files line by line",
                "patch": "Apply diff files"
            },
            "Package Management": {
                "kapp": "Package manager",
                "kapp-search": "Search packages",
                "kapp-info": "Show package info",
                "kapp-update": "Update package database"
            },
            "System Information": {
                "uname": "Print system information",
                "uptime": "Show system uptime",
                "df": "Report disk space usage",
                "free": "Display memory usage",
                "date": "Display/set system date",
                "sysinfo": "Show system statistics"
            },
            "Network Tools": {
                "ping": "Test network connectivity",
                "netstat": "Network statistics",
                "wget": "Retrieve files via HTTP",
                "curl": "Transfer data via protocols",
                "ifconfig": "Configure network interface",
                "route": "Show/manipulate routing table"
            },
            "File Compression": {
                "tar": "Archive files",
                "gzip": "Compress/decompress files",
                "zip": "Package/compress files",
                "unzip": "Extract compressed files",
                "bzip2": "Block-sorting compression",
                "xz": "LZMA compression"
            },
            "Disk Management": {
                "disk": "Manage disks"
            }
        }

        self.intro = self._get_intro()
        self.prompt = self._get_prompt()
        logger.info("Enhanced shell initialized with extended features")

    def get_resource_value(self, resource_dict: Dict, *keys: str) -> float:
        """Safely get nested resource values with type checking"""
        try:
            value = resource_dict
            for key in keys:
                value = value[key]
            return float(value) if isinstance(value, (int, float)) else 0.0
        except (KeyError, TypeError, ValueError):
            return 0.0

    def _get_intro(self) -> str:
        """Generate enhanced intro message with system info"""
        try:
            resources = self.process_mgr.get_system_resources()
            cpu_percent = self.get_resource_value(resources, 'cpu', 'percent')
            mem_percent = self.get_resource_value(resources, 'memory',
                                                  'virtual', 'percent')
            disk_percent = self.get_resource_value(resources, 'disk', 'usage',
                                                   'percent')

            return f"""
╔══════════════════════════════════════════════════════════╗
║                 Welcome to Kaede OS (KOS)                ║
║                                                         ║
║  System Information:                                    ║
║  - CPU Usage: {cpu_percent:.1f}%                                  ║
║  - Memory: {mem_percent:.1f}% used                              ║
║  - Disk: {disk_percent:.1f}% used                                ║
║                                                         ║
║  Type 'help' for commands, 'intro' for system info     ║
╚══════════════════════════════════════════════════════════╝
"""
        except Exception as e:
            logger.error(f"Error generating intro: {e}")
            return "Welcome to KOS. Type 'help' for commands.\n"

    def _get_prompt(self) -> str:
        """Generate enhanced shell prompt with git-like info"""
        cwd = self.fs.current_path
        
        # Show just the directory name for non-root paths, or "/" for root
        if cwd == "/":
            display_path = "/"
        else:
            display_path = os.path.basename(cwd) or "/"

        time_str = datetime.now().strftime("%H:%M")
        branch = "main"  # TODO: Implement git integration

        if self.us.current_user == "kaede":
            return f"\033[1;31m[{time_str} root@kos {display_path} ({branch})]#\033[0m "
        return f"\033[1;34m[{time_str} {self.us.current_user}@kos {display_path} ({branch})]$\033[0m "

    def _setup_signal_handlers(self):
        """Setup enhanced signal handling"""
        signal.signal(signal.SIGINT, self._handle_sigint)
        signal.signal(signal.SIGTERM, self._handle_sigterm)

    def _handle_sigint(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        if self.console:
            self.console.print("\n^C")
        else:
            print("\n^C")
        return

    def _handle_sigterm(self, signum, frame):
        """Handle termination signal"""
        if self.console:
            self.console.print("\nReceived SIGTERM, cleaning up...")
        else:
            print("\nReceived SIGTERM, cleaning up...")
        self._cleanup()
        sys.exit(0)

    def _init_package_cli_integration(self):
        """Initialize package CLI command integration"""
        try:
            from kos.package.cli_integration import integrate_with_shell
            self.package_cli_integration = integrate_with_shell(self)
            logger.info("Package CLI integration initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize package CLI integration: {e}")
            self.package_cli_integration = None

    def _cleanup(self):
        """Cleanup resources before exit"""
        try:
            self.executor.shutdown(wait=False)
            self.us.save_users()
            logger.info("Shell cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def register_command(self, command_name: str, command_func: callable, help_text: str = ""):
        """Register a new command with the shell
        
        Args:
            command_name: Name of the command
            command_func: Function to execute for the command
            help_text: Help text for the command
        """
        # Create a do_ method dynamically
        def do_method(self, arg):
            try:
                return command_func(self, arg)
            except Exception as e:
                self._print_error(f"Error executing {command_name}: {e}")
        
        # Set the method on the shell instance
        setattr(self, f"do_{command_name}", do_method.__get__(self, self.__class__))
        
        # Add help if provided
        if help_text:
            def help_method(self):
                self._print_info(help_text)
            setattr(self, f"help_{command_name}", help_method.__get__(self, self.__class__))
        
        logger.debug(f"Registered command: {command_name}")

    def default(self, line):
        """Handle unknown commands - check if they're package commands"""
        try:
            # Split command and arguments
            parts = line.split()
            if not parts:
                return
            
            command_name = parts[0]
            args = parts[1:] if len(parts) > 1 else []
            
            # Check if it's a package command
            if self.package_cli_integration:
                if self.package_cli_integration.command_manager.is_command_available(command_name):
                    success = self.package_cli_integration.command_manager.execute_command(command_name, args)
                    return
            
            # Try to find similar commands (typo correction)
            suggestion = self._find_similar_command(command_name)
            if suggestion:
                print(f"Command '{command_name}' not found. Did you mean '{suggestion}'?")
                # Ask if user wants to run the suggested command
                response = input(f"Run '{suggestion} {' '.join(args)}'? (y/N): ")
                if response.lower() == 'y':
                    self.onecmd(f"{suggestion} {' '.join(args)}")
            else:
                print(f"*** Unknown syntax: {command_name}")
            
        except Exception as e:
            logger.error(f"Error in default command handler: {e}")
            print(f"*** Unknown syntax: {line}")

    def do_clear(self, arg):
        """Clear the terminal screen"""
        if self.console:
            self.console.clear()
        else:
            os.system('cls' if os.name == 'nt' else 'clear')
        if RICH_AVAILABLE and self.console:
            print(self.intro)
        else:
            print("Welcome to Kaede OS Shell")

    def do_ps(self, arg):
        """Enhanced process status display"""
        try:
            args = shlex.split(arg)
            show_all = '-e' in args
            full_format = '-f' in args
            tree_view = '-t' in args
            watch_mode = '-w' in args

            if watch_mode:
                self._watch_processes(full_format)
            elif tree_view:
                processes = self.process_mgr.get_process_tree()
                self._display_process_tree(processes)
            else:
                processes = self.process_mgr.list_processes(refresh=True)
                self._display_process_list(processes, full_format)

        except Exception as e:
            logger.error(f"Error in ps command: {e}")
            print(f"ps: {str(e)}")

    def _watch_processes(self, full_format: bool):
        """Watch process list in real-time"""
        try:
            if RICH_AVAILABLE and self.console:
                with Progress(SpinnerColumn(),
                              *Progress.get_default_columns(),
                              TimeElapsedColumn(),
                              refresh_per_second=4) as progress:
                    while True:
                        self.console.clear()
                        processes = self.process_mgr.list_processes(
                            refresh=True)
                        resources = self.process_mgr.get_system_resources()

                        self.console.print(
                            Panel(
                                f"CPU: {self.get_resource_value(resources, 'cpu', 'percent'):.1f}% | "
                                f"MEM: {self.get_resource_value(resources, 'memory', 'virtual', 'percent'):.1f}% | "
                                f"Processes: {len(processes)}"))

                        self._display_process_list(processes, full_format)
                        time.sleep(2)
            else:
                while True:
                    processes = self.process_mgr.list_processes(refresh=True)
                    print("Process list:")
                    for p in processes:
                        print(f"  PID: {p.pid}, Name: {p.name}")
                    time.sleep(2)
        except KeyboardInterrupt:
            return

    def _display_process_tree(self,
                              tree: Dict[int, List[Any]],
                              pid: int = 1,
                              level: int = 0):
        """Display process tree with enhanced formatting"""
        if pid not in tree:
            return

        for process in tree[pid]:
            prefix = "  " * level + ("├─" if level > 0 else "")
            status_color = {
                'running': 'green',
                'sleeping': 'blue',
                'stopped': 'yellow',
                'zombie': 'red'
            }.get(process.status.lower(), 'white')

            if RICH_AVAILABLE and self.console:
                self.console.print(f"{prefix} {process.pid} ", end="")
                self.console.print(
                    f"[{status_color}]{process.name}[/{status_color}] "
                    f"({process.cpu_percent:.1f}% CPU, {process.memory_percent:.1f}% MEM)"
                )
            else:
                print(
                    f"{prefix} {process.pid} {process.name} ({process.cpu_percent:.1f}% CPU, {process.memory_percent:.1f}% MEM)"
                )
            self._display_process_tree(tree, process.pid, level + 1)

    def _display_process_list(self, processes: List[Any], full_format: bool):
        """Display process list with enhanced formatting"""
        if RICH_AVAILABLE and self.console:
            table = Table(title="Process List")

            if full_format:
                columns = [
                    "PID", "PPID", "USER", "PRI", "NI", "CPU%", "MEM%", "THR",
                    "START", "TIME", "COMMAND"
                ]
            else:
                columns = ["PID", "TTY", "STAT", "TIME", "CMD"]

            for col in columns:
                table.add_column(col)

            sorted_processes = sorted(
                processes,
                key=lambda p: p.cpu_percent + p.memory_percent,
                reverse=True)

            for proc in sorted_processes[:20]:  # Show top 20 by default
                if full_format:
                    table.add_row(
                        str(proc.pid), str(proc.ppid), proc.username,
                        str(proc.priority), str(proc.nice),
                        f"{proc.cpu_percent:.1f}",
                        f"{proc.memory_percent:.1f}", str(proc.threads),
                        proc.create_time.strftime("%H:%M"),
                        self._format_proc_time(proc),
                        " ".join(proc.cmdline) if proc.cmdline else proc.name)
                else:
                    table.add_row(str(proc.pid), "?", proc.status[:1], "00:00",
                                  proc.name)

            self.console.print(table)
        else:
            print("Process List:")
            for p in processes:
                print(f"  PID: {p.pid}, Name: {p.name}")

    def _format_proc_time(self, proc: Any) -> str:
        """Format process time prettily"""
        if hasattr(proc, 'cpu_times'):
            cpu_time = proc.cpu_times()
            return f"{int(cpu_time.user + cpu_time.system)}:{int((cpu_time.user + cpu_time.system) * 60 % 60):02d}"
        return "00:00"

    def do_top(self, arg):
        """Interactive process viewer"""
        try:
            if RICH_AVAILABLE and self.console:
                with Progress(SpinnerColumn(),
                              *Progress.get_default_columns(),
                              TimeElapsedColumn(),
                              refresh_per_second=4) as progress:
                    while True:
                        processes = self.process_mgr.list_processes(
                            refresh=True)
                        resources = self.process_mgr.get_system_resources()

                        self.console.clear()
                        self.console.print(
                            f"KOS Top - {datetime.now().strftime('%H:%M:%S')}")
                        self.console.print(
                            f"CPU: {self.get_resource_value(resources, 'cpu', 'percent'):.1f}% MEM: {self.get_resource_value(resources, 'memory', 'virtual', 'percent'):.1f}%"
                        )

                        table = Table(title="Process List")
                        columns = [
                            "PID", "USER", "PR", "CPU%", "MEM%", "COMMAND"
                        ]
                        for col in columns:
                            table.add_column(col)

                        for proc in sorted(processes,
                                           key=lambda p: p.cpu_percent,
                                           reverse=True)[:20]:
                            table.add_row(str(proc.pid), proc.username,
                                          str(proc.priority),
                                          f"{proc.cpu_percent:.1f}",
                                          f"{proc.memory_percent:.1f}",
                                          proc.name)

                        self.console.print(table)
                        time.sleep(2)
            else:
                while True:
                    processes = self.process_mgr.list_processes(refresh=True)
                    print("Top processes:")
                    for p in sorted(processes,
                                    key=lambda p: p.cpu_percent,
                                    reverse=True)[:10]:
                        print(
                            f"  PID: {p.pid}, Name: {p.name}, CPU%: {p.cpu_percent:.1f}"
                        )
                    time.sleep(2)
        except KeyboardInterrupt:
            return
        except Exception as e:
            logger.error(f"Error in top command: {e}")
            print(f"top: {str(e)}")

    def _load_history_from_manager(self):
        """Load command history from custom manager"""
        try:
            # Load recent history into local cache
            entries = self.history_manager.get_history(limit=1000)
            self.history = [entry.command for entry in entries]
        except Exception as e:
            logger.warning(f"Error loading command history: {e}")
    
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings"""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # j+1 instead of j since previous_row and current_row are one character longer
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def _find_similar_command(self, command: str) -> Optional[str]:
        """Find similar command using Levenshtein distance"""
        # Get all available commands
        all_commands = []
        
        # Built-in shell commands
        for attr in dir(self):
            if attr.startswith('do_'):
                cmd_name = attr[3:]
                all_commands.append(cmd_name)
        
        # Package commands
        if self.package_cli_integration:
            all_commands.extend(self.package_cli_integration.command_manager.list_commands())
        
        # Find the closest match
        min_distance = float('inf')
        best_match = None
        
        for cmd in all_commands:
            distance = self._levenshtein_distance(command.lower(), cmd.lower())
            # Only suggest if the distance is reasonable (less than half the length)
            if distance < min_distance and distance <= len(command) // 2 + 1:
                min_distance = distance
                best_match = cmd
        
        return best_match

    def precmd(self, line):
        """Preprocess command line before execution"""
        if line.strip():
            # Record start time for duration tracking
            self._cmd_start_time = time.time()
        return line

    def postcmd(self, stop, line):
        """Save command history after execution"""
        if line.strip():
            # Calculate duration
            duration = time.time() - getattr(self, '_cmd_start_time', time.time())
            
            # Add to custom history manager
            self.history_manager.add_entry(line, exit_code=0, duration=duration)
            
            # Update local cache
            self.history.append(line)
            if len(self.history) > self.MAX_HISTORY:
                self.history.pop(0)
        
        return stop

    def do_disk(self, arg):
        """
        Disk management utility
        Usage: disk [command] [options]
        Commands:
          usage    - Show disk usage statistics
          check    - Check filesystem integrity
          repair   - Attempt to repair filesystem issues
        """
        try:
            args = shlex.split(arg) if arg else []
            command = args[0] if args else 'usage'

            if command == 'usage':
                resources = self.process_mgr.get_system_resources()
                disk_info = resources.get('disk', {})
                usage = disk_info.get('usage', {})

                if not RICH_AVAILABLE or not self.console:
                    # Fallback to basic output if rich is not available
                    print("\nDisk Usage:")
                    print(
                        f"Total Space: {usage.get('total', 0)/1024/1024:.2f} MB"
                    )
                    print(
                        f"Used Space: {usage.get('used', 0)/1024/1024:.2f} MB")
                    print(
                        f"Free Space: {usage.get('free', 0)/1024/1024:.2f} MB")
                    print(f"Usage: {usage.get('percent', 0):.1f}%")
                    return

                table = Table(title="Disk Usage")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="magenta")

                table.add_row("Total Space",
                              f"{usage.get('total', 0)/1024/1024:.2f} MB")
                table.add_row("Used Space",
                              f"{usage.get('used', 0)/1024/1024:.2f} MB")
                table.add_row("Free Space",
                              f"{usage.get('free', 0)/1024/1024:.2f} MB")
                table.add_row("Usage", f"{usage.get('percent', 0):.1f}%")

                if io_info := disk_info.get('io'):
                    table.add_row("Read Operations",
                                  str(io_info.get('read_count', 0)))
                    table.add_row("Write Operations",
                                  str(io_info.get('write_count', 0)))

                self.console.print(table)

            elif command == 'check':
                if not self.fs.disk_manager:
                    print("Error: Disk manager not initialized")
                    return

                issues = self.fs.disk_manager.check_integrity()
                if not issues:
                    if RICH_AVAILABLE and self.console:
                        self.console.print(
                            "[green]✓ Filesystem integrity check passed[/green]"
                        )
                    else:
                        print("✓ Filesystem integrity check passed")
                else:
                    if RICH_AVAILABLE and self.console:
                        self.console.print(
                            "[red]! Filesystem integrity issues found:[/red]")
                    else:
                        print("! Filesystem integrity issues found:")
                    for issue in issues:
                        print(f"  - {issue}")

            elif command == 'repair':
                if not self.fs.disk_manager:
                    print("Error: Disk manager not initialized")
                    return

                if self.fs.disk_manager.repair_filesystem():
                    if RICH_AVAILABLE and self.console:
                        self.console.print(
                            "[green]✓ Filesystem repair completed successfully[/green]"
                        )
                    else:
                        print("✓ Filesystem repair completed successfully")
                else:
                    if RICH_AVAILABLE and self.console:
                        self.console.print(
                            "[red]✗ Failed to repair filesystem[/red]")
                    else:
                        print("✗ Failed to repair filesystem")

            else:
                print(
                    "Invalid disk command. Available commands: usage, check, repair"
                )

        except Exception as e:
            logger.error(f"Error in disk command: {e}")
            print(f"disk: {str(e)}")

    def do_users(self, arg):
        """Display information about system users and their status"""
        try:
            if RICH_AVAILABLE and self.console:
                table = Table(title="System Users")
                table.add_column("Username", style="cyan")
                table.add_column("Status", style="magenta")
                table.add_column("Groups", style="green")
                table.add_column("Home", style="blue")

                statuses = self.us.get_user_status()
                for username, status in statuses.items():
                    user_info = self.us.get_user_info(username)
                    table.add_row(username, status,
                                  ", ".join(user_info["groups"]),
                                  user_info["home"])

                self.console.print(table)
            else:
                statuses = self.us.get_user_status()
                print("System Users:")
                for username, status in statuses.items():
                    print(f"  Username: {username}, Status: {status}")

        except Exception as e:
            logger.error(f"Error in users command: {e}")
            print(f"users: {str(e)}")

    def do_ls(self, arg):
        """List directory contents with enhanced formatting"""
        try:
            args = shlex.split(arg)
            path = "." if not args else args[0]
            long_format = "-l" in args

            entries = self.fs.list_directory(path, long_format=long_format)

            if RICH_AVAILABLE and self.console:
                table = Table(title=f"Contents of {path}")
                if long_format:
                    table.add_column("Type")
                    table.add_column("Permissions")
                    table.add_column("Owner")
                    table.add_column("Group")
                    table.add_column("Size")
                    table.add_column("Modified")
                    table.add_column("Name")

                    for entry in entries:
                        table.add_row(
                            "d" if entry['type'] == 'dir' else '-',
                            oct(entry['permissions'])[2:], entry['owner'],
                            entry['group'], str(entry['size']),
                            entry['modified'].strftime("%Y-%m-%d %H:%M"),
                            entry['name'])
                else:
                    table.add_column("Name")
                    for entry in entries:
                        table.add_row(
                            entry if isinstance(entry, str) else entry['name'])

                self.console.print(table)
            else:
                if long_format:
                    for entry in entries:
                        print(
                            f"{entry['type']} {oct(entry['permissions'])[2:]} {entry['owner']} {entry['group']} {entry['size']} {entry['modified']} {entry['name']}"
                        )
                else:
                    print("  ".join(entries if isinstance(entries[0], str) else
                                    [e['name'] for e in entries]))

        except Exception as e:
            logger.error(f"Error in ls command: {e}")
            print(f"ls: {str(e)}")

    def do_cd(self, arg):
        """Change directory with path completion"""
        try:
            path = arg.strip() or "~"
            if path == "~":
                path = f"/home/{self.us.current_user}"

            # Use the filesystem's change_directory method for proper validation
            self.fs.change_directory(path)
            self.prompt = self._get_prompt()  # Update prompt with new path

        except Exception as e:
            print(f"cd: {str(e)}")

    def do_pwd(self, arg):
        """Print working directory"""
        print(self.fs.current_path)

    def do_mkdir(self, arg):
        """Create directory with permissions"""
        try:
            args = shlex.split(arg)
            if not args:
                print("mkdir: missing operand")
                return

            path = args[0]
            # Note: Mode is not used since the filesystem only supports mkdir with default permissions
            # If we need to support mode, we'll need to enhance the BaseFileSystem.mkdir method

            # Call the filesystem's mkdir method
            self.fs.mkdir(path)
            logger.info(f"Created directory: {path}")

        except Exception as e:
            logger.error(f"Error in mkdir command: {e}")
            print(f"mkdir: {str(e)}")

    def do_whoami(self, arg):
        """Display current user"""
        print(self.us.current_user)

    def do_su(self, arg):
        """Switch user"""
        try:
            target_user = arg.strip() or "kaede"
            password = input("Password: ")

            if self.us.authenticate(target_user, password):
                print(f"Switched to user {target_user}")
                self.prompt = self._get_prompt()
            else:
                print("Authentication failed")

        except Exception as e:
            logger.error(f"Error in su command: {e}")
            print(f"su: {str(e)}")

    def do_useradd(self, arg):
        """Add new user"""
        try:
            args = shlex.split(arg)
            if not args:
                print("useradd: missing username")
                return

            username = args[0]
            groups = args[1:] if len(args) > 1 else None
            password = input("Enter password: ")

            if self.us.add_user(username, password, groups):
                print(f"User {username} created successfully")
            else:
                print(f"Failed to create user {username}")

        except Exception as e:
            logger.error(f"Error in useradd command: {e}")
            print(f"useradd: {str(e)}")

    def do_exit(self, arg):
        """Exit the shell"""
        self._cleanup()
        print("Exiting KOS Shell...")
        return True

    def do_EOF(self, arg):
        """Exit the shell on end of file"""
        return self.do_exit(arg)

    def do_cat(self, arg):
        """Display file contents with syntax highlighting"""
        try:
            args = shlex.split(arg)
            if not args:
                print("cat: missing file operand")
                return

            path = args[0]
            content = self.fs.read_file(path)

            if RICH_AVAILABLE and self.console:
                # Try to detect the file type for syntax highlighting
                file_ext = os.path.splitext(path)[1].lower()
                if file_ext in ['.py', '.sh', '.json', '.txt', '.md']:
                    syntax = Syntax(content, file_ext[1:], theme="monokai")
                    self.console.print(syntax)
                else:
                    self.console.print(content)
            else:
                print(content)

        except Exception as e:
            logger.error(f"Error in cat command: {e}")
            print(f"cat: {str(e)}")

    def do_rm(self, arg):
        """Remove files or directories"""
        try:
            args = shlex.split(arg)
            if not args:
                print("rm: missing operand")
                return

            path = args[0]
            recursive = "-r" in args or "-R" in args

            # Check if file exists
            node = self.fs._get_node(self.fs._resolve_path(path))
            if not node:
                print(f"rm: cannot remove '{path}': No such file or directory")
                return

            # Check if directory and recursive flag
            if node.type == 'directory' and not recursive:
                print(
                    f"rm: cannot remove '{path}': Is a directory, use -r for recursive removal"
                )
                return

            # Remove file/directory
            if node.parent:
                if node.name in node.parent.content:
                    del node.parent.content[node.name]
                    node.parent.metadata['modified'] = datetime.now()
                    logger.info(f"Removed {path}")

        except Exception as e:
            logger.error(f"Error in rm command: {e}")
            print(f"rm: {str(e)}")
            
    def do_nano(self, arg):
        """Nano-like text editor
        
        Usage: nano [options] [filename]
        
        Opens the specified file in the nano editor. If the file doesn't exist,
        it will be created when saved.
        
        Options:
          --help            Show this help message and exit
          --linenumbers    Enable line numbers (default: enabled)
          --nolinenumbers  Disable line numbers
          --autoindent     Enable auto-indentation (default: enabled)
          --noautoindent   Disable auto-indentation
          --backup         Create backup files (default: enabled)
          --nobackup       Disable backup files
          --autosave       Enable auto-save
          --noautosave     Disable auto-save (default)
        
        Keyboard shortcuts:
          Navigation: Arrow keys, Home/End, Page Up/Down
          File: ^O (Save), ^R (Read file), ^X (Exit)
          Edit: ^K (Cut line), ^U (Paste), ^W (Search), ^F (Find next), ^G (Help)
          Advanced: Alt+N (Toggle line numbers), Alt+I (Auto-indent), Alt+< & Alt+> (Switch buffers)
                   Alt+U (Undo), Alt+E (Redo), Alt+B (Backup), Alt+A (Auto-save)
        """
        try:
            args = shlex.split(arg)
            
            # Process --help option
            if not args or '--help' in args:
                print(self.do_nano.__doc__)
                return
            
            # Parse options and filename
            options = {}
            filename = None
            
            for arg in args:
                if arg.startswith('--'):
                    # Process options
                    if arg == '--linenumbers':
                        options['linenumbers'] = True
                    elif arg == '--nolinenumbers':
                        options['linenumbers'] = False
                    elif arg == '--autoindent':
                        options['autoindent'] = True
                    elif arg == '--noautoindent':
                        options['autoindent'] = False
                    elif arg == '--backup':
                        options['backup'] = True
                    elif arg == '--nobackup':
                        options['backup'] = False
                    elif arg == '--autosave':
                        options['autosave'] = True
                    elif arg == '--noautosave':
                        options['autosave'] = False
                else:
                    # Treat as filename
                    filename = arg
            
            if not filename:
                print("nano: missing file operand")
                print("Try 'nano --help' for more information.")
                return
            
            # Resolve the full path
            path = os.path.join(self.fs.cwd, filename) if not os.path.isabs(filename) else filename
            
            # Check if the parent directory exists
            parent_dir = os.path.dirname(path)
            if parent_dir and not self.fs.exists(parent_dir):
                print(f"nano: cannot open '{filename}': No such file or directory")
                return
                
            # Check if path is a directory
            if self.fs.exists(path) and self.fs.is_dir(path):
                print(f"nano: {path}: Is a directory")
                return
                
            # Run the nano editor with options
            try:
                nano_editor(self.fs, path, **options)
            except ImportError as e:
                print("nano: The 'windows-curses' package is required for the nano editor.")
                print("Install it with: pip install windows-curses")
                logger.error("Missing windows-curses package: %s", e)
            except Exception as e:
                print(f"nano: An error occurred: {str(e)}")
                logger.exception("Error in nano editor")
                
        except Exception as e:
            print(f"nano: {str(e)}")
            logger.error("Error in nano command: %s", e)
            
    def do_touch(self, arg):
        """Create a new empty file or update file timestamp"""
        try:
            args = shlex.split(arg)
            if not args:
                print("touch: missing file operand")
                return

            path = args[0]
            success, message = touch_file(self.fs, path)
            if not success:
                print(f"touch: {message}")
                
        except Exception as e:
            logger.error(f"Error in touch command: {e}")
            print(f"touch: {str(e)}")
            
    def do_find(self, arg):
        """Find files matching a pattern"""
        try:
            args = shlex.split(arg)
            if not args:
                print("find: missing path operand")
                return

            path = args[0]
            pattern = "*"
            max_depth = None
            
            # Parse arguments
            i = 1
            while i < len(args):
                if args[i] == "-name" and i + 1 < len(args):
                    pattern = args[i + 1]
                    i += 2
                elif args[i] == "-maxdepth" and i + 1 < len(args):
                    try:
                        max_depth = int(args[i + 1])
                        i += 2
                    except ValueError:
                        print(f"find: invalid maximum depth: {args[i + 1]}")
                        return
                else:
                    i += 1
            
            results = find_files(self.fs, path, pattern, max_depth)
            
            if RICH_AVAILABLE and self.console:
                table = Table(title=f"Find Results for '{pattern}'")
                table.add_column("Path", style="cyan")
                
                for file_path in results:
                    table.add_row(file_path)
                    
                self.console.print(table)
            else:
                if results:
                    for file_path in results:
                        print(file_path)
                else:
                    print("No files found")
                
        except Exception as e:
            logger.error(f"Error in find command: {e}")
            print(f"find: {str(e)}")
            
    def do_grep(self, arg):
        """Search for pattern in files"""
        try:
            args = shlex.split(arg)
            if len(args) < 2:
                print("grep: missing pattern and file operand")
                print("Usage: grep [options] PATTERN FILE")
                return

            pattern = args[0]
            path = args[1]
            case_sensitive = True
            
            # Check for case insensitive flag
            if "-i" in args:
                case_sensitive = False
            
            results = grep_text(self.fs, pattern, path, case_sensitive)
            
            if RICH_AVAILABLE and self.console:
                table = Table(title=f"Grep Results for '{pattern}'")
                table.add_column("File", style="cyan")
                table.add_column("Line", style="green")
                table.add_column("Content", style="white")
                
                for file_path, line_num, content in results:
                    table.add_row(file_path, str(line_num), content)
                    
                self.console.print(table)
            else:
                if results:
                    for file_path, line_num, content in results:
                        print(f"{file_path}:{line_num}: {content}")
                else:
                    print("No matches found")
                
        except Exception as e:
            logger.error(f"Error in grep command: {e}")
            print(f"grep: {str(e)}")
            
    def do_pip(self, arg):
        """Manage Python packages with pip"""
        try:
            if not arg:
                print("Usage: pip COMMAND [OPTIONS]")
                print("Commands:")
                print("  install PACKAGE    Install a package")
                print("  uninstall PACKAGE  Uninstall a package")
                print("  list              List installed packages")
                print("  show PACKAGE      Show information about a package")
                print("  search QUERY      Search for packages")
                return

            args = shlex.split(arg)
            command = args[0].lower()
            
            if command == "install" and len(args) > 1:
                package = args[1]
                upgrade = "--upgrade" in args or "-U" in args
                success, message = PipCommandHandler.install(package, upgrade)
                print(message)
                
            elif command == "uninstall" and len(args) > 1:
                package = args[1]
                success, message = PipCommandHandler.uninstall(package)
                print(message)
                
            elif command == "list":
                success, message = PipCommandHandler.list_packages()
                if message:
                    print(message)
                    
            elif command == "show" and len(args) > 1:
                package = args[1]
                success, message = PipCommandHandler.show(package)
                print(message)
                
            elif command == "search" and len(args) > 1:
                query = args[1]
                success, message = PipCommandHandler.search(query)
                print(message)
                
            else:
                print(f"pip: unknown command '{command}'")
                print("Try 'pip' without arguments for help")
                
        except Exception as e:
            logger.error(f"Error in pip command: {e}")
            print(f"pip: {str(e)}")
            
    def do_help(self, arg):
        """List available commands by category or show help for a specific command"""
        if arg:
            # Show help for specific command
            return super().do_help(arg)
        
        # Define additional command categories that weren't in the original self.command_categories
        additional_categories = {
            "Package Management": {
                "pip": "Manage Python packages with pip",
                "kpm": "Install/remove KOS packages",
            },
            "System Monitor": {
                "top": "Interactive process viewer", 
                "free": "Display memory usage",
                "sysinfo": "Show system statistics",
            },
            "Disk Management": {
                "disk": "Disk management utility",
            },
        }
        
        # Combine all categories
        all_categories = {**self.command_categories, **additional_categories}
        
        # Get all methods that start with do_
        commands = {}
        for name in dir(self):
            if name.startswith('do_'):
                cmd_name = name[3:]
                if cmd_name not in ['EOF', 'shell']:
                    method = getattr(self, name)
                    doc = method.__doc__ or ''
                    commands[cmd_name] = doc.strip()
        
        if RICH_AVAILABLE and self.console:
            # Rich formatted output
            self.console.print("\n[bold cyan]KOS Shell Commands[/bold cyan]\n")
            
            for category, category_commands in all_categories.items():
                # Only show categories that have commands
                has_commands = False
                for cmd_name in category_commands:
                    if cmd_name in commands:
                        has_commands = True
                        break
                        
                if has_commands:
                    table = Table(title=category)
                    table.add_column("Command", style="green")
                    table.add_column("Description", style="yellow")
                    
                    for cmd_name, description in sorted(category_commands.items()):
                        if cmd_name in commands:
                            table.add_row(cmd_name, description)
                    
                    self.console.print(table)
                    self.console.print("")
            
            # Show uncategorized commands
            uncategorized = set(commands.keys())
            for category in all_categories.values():
                for cmd_name in category:
                    if cmd_name in uncategorized:
                        uncategorized.remove(cmd_name)
            
            if uncategorized:
                table = Table(title="Other Commands")
                table.add_column("Command", style="green")
                table.add_column("Description", style="yellow")
                
                for cmd_name in sorted(uncategorized):
                    table.add_row(cmd_name, commands[cmd_name])
                
                self.console.print(table)
        else:
            # Plain text output
            print("\nKOS Shell Commands\n")
            
            for category, category_commands in all_categories.items():
                has_commands = False
                for cmd_name in category_commands:
                    if cmd_name in commands:
                        has_commands = True
                        break
                        
                if has_commands:
                    print(f"\n{category}:")
                    
                    for cmd_name, description in sorted(category_commands.items()):
                        if cmd_name in commands:
                            print(f"  {cmd_name.ljust(15)} {description}")
            
            # Show uncategorized commands
            uncategorized = set(commands.keys())
            for category in all_categories.values():
                for cmd_name in category:
                    if cmd_name in uncategorized:
                        uncategorized.remove(cmd_name)
            
            if uncategorized:
                print("\nOther Commands:")
                for cmd_name in sorted(uncategorized):
                    print(f"  {cmd_name.ljust(15)} {commands[cmd_name]}")
                    
        print("\nFor help on a specific command, type: help COMMAND")
        return False

    def do_monitor(self, arg):
        """Monitor system resource usage over time"""
        try:
            args = shlex.split(arg)
            resource_type = "cpu"  # Default resource to monitor
            interval = 1  # Default sampling interval in seconds
            duration = 10  # Default monitoring duration in seconds
            
            if args:
                resource_type = args[0].lower()
                
            # Parse optional arguments
            i = 1
            while i < len(args):
                if args[i] == "-i" or args[i] == "--interval" and i + 1 < len(args):
                    try:
                        interval = max(0.1, float(args[i + 1]))
                        i += 2
                    except ValueError:
                        print(f"monitor: invalid interval: {args[i + 1]}")
                        return
                elif args[i] == "-d" or args[i] == "--duration" and i + 1 < len(args):
                    try:
                        duration = max(1, int(args[i + 1]))
                        i += 2
                    except ValueError:
                        print(f"monitor: invalid duration: {args[i + 1]}")
                        return
                else:
                    i += 1
            
            if resource_type not in ["cpu", "memory", "disk", "network"]:
                print(f"monitor: invalid resource type: {resource_type}")
                print("Valid resource types: cpu, memory, disk, network")
                return
                
            print(f"Monitoring {resource_type} resource usage for {duration} seconds (sampling every {interval} seconds)...")
            
            if RICH_AVAILABLE and self.console:
                # Rich formatted live monitoring
                from rich.live import Live
                from rich.layout import Layout
                from rich.panel import Panel
                
                layout = Layout()
                
                def update_display(sample):
                    # Update the display with new sample data
                    content = f"[bold]Timestamp:[/bold] {sample['timestamp']}\n\n"
                    
                    if resource_type == "cpu":
                        data = sample["data"]
                        content += f"CPU Usage: [bold green]{data['percent']}%[/bold green]\n"
                        if data['freq']:
                            content += f"Frequency: {data['freq']['current']}MHz\n"
                        content += f"Cores: {data['count']}\n"
                        
                    elif resource_type == "memory":
                        virtual = sample["data"]["virtual"]
                        swap = sample["data"]["swap"]
                        content += f"Memory Usage: [bold green]{virtual['percent']}%[/bold green]\n"
                        content += f"Total: {virtual['total'] / 1024 / 1024:.1f}MB\n"
                        content += f"Available: {virtual['available'] / 1024 / 1024:.1f}MB\n"
                        content += f"Used: {virtual['used'] / 1024 / 1024:.1f}MB\n"
                        content += f"\nSwap Usage: {swap['percent']}%\n"
                        
                    elif resource_type == "disk":
                        usage = sample["data"]["usage"]
                        content += f"Disk Usage: [bold green]{usage['percent']}%[/bold green]\n"
                        content += f"Total: {usage['total'] / 1024 / 1024:.1f}MB\n"
                        content += f"Used: {usage['used'] / 1024 / 1024:.1f}MB\n"
                        content += f"Free: {usage['free'] / 1024 / 1024:.1f}MB\n"
                        
                    elif resource_type == "network":
                        if sample["data"]["io"]:
                            io = sample["data"]["io"]
                            content += f"Bytes Sent: {io['bytes_sent'] / 1024:.1f}KB\n"
                            content += f"Bytes Received: {io['bytes_recv'] / 1024:.1f}KB\n"
                            content += f"Packets Sent: {io['packets_sent']}\n"
                            content += f"Packets Received: {io['packets_recv']}\n"
                        content += f"Network Connections: {sample['data']['connections']}\n"
                        
                    layout.update(Panel(content, title=f"{resource_type.title()} Monitoring"))
                
                # Start live display
                with Live(layout, refresh_per_second=4) as live:
                    SystemMonitor.monitor_resource(resource_type, interval, duration, update_display)
            else:
                # Plain text monitoring
                def print_sample(sample):
                    print(f"\nTimestamp: {sample['timestamp']}")
                    
                    if resource_type == "cpu":
                        print(f"CPU Usage: {sample['data']['percent']}%")
                    elif resource_type == "memory":
                        print(f"Memory Usage: {sample['data']['virtual']['percent']}%")
                    elif resource_type == "disk":
                        print(f"Disk Usage: {sample['data']['usage']['percent']}%")
                    elif resource_type == "network":
                        if sample["data"]["io"]:
                            print(f"Network I/O: {sample['data']['io']['bytes_recv']/1024:.1f}KB received, {sample['data']['io']['bytes_sent']/1024:.1f}KB sent")
                
                SystemMonitor.monitor_resource(resource_type, interval, duration, print_sample)
                
        except KeyboardInterrupt:
            print("Monitoring interrupted by user")
        except Exception as e:
            logger.error(f"Error in monitor command: {e}")
            print(f"monitor: {str(e)}")
            
    def do_procinfo(self, arg):
        """Display detailed information about a process"""
        try:
            args = shlex.split(arg)
            if not args:
                print("procinfo: missing process ID")
                print("Usage: procinfo PID")
                return

            try:
                pid = int(args[0])
            except ValueError:
                print(f"procinfo: invalid process ID: {args[0]}")
                return
                
            process_info = SystemMonitor.get_process_info(pid)
            
            if 'error' in process_info:
                print(f"procinfo: {process_info['error']}")
                return
                
            if RICH_AVAILABLE and self.console:
                # Rich formatted output
                table = Table(title=f"Process {pid} Information")
                table.add_column("Property", style="cyan")
                table.add_column("Value", style="green")
                
                for key, value in process_info.items():
                    if key != 'pid':  # Skip PID since it's in the title
                        table.add_row(key, str(value))
                        
                self.console.print(table)
            else:
                # Plain text output
                print(f"\nProcess {pid} Information:")
                for key, value in process_info.items():
                    if key != 'pid':  # Skip PID since it's in the title
                        print(f"  {key}: {value}")
                        
        except Exception as e:
            logger.error(f"Error in procinfo command: {e}")
            print(f"procinfo: {str(e)}")
            
    def do_kill(self, arg):
        """Kill a process by PID"""
        try:
            args = shlex.split(arg)
            if not args:
                print("kill: missing process ID")
                print("Usage: kill [-f] PID")
                return

            force = "-f" in args
            # Filter out options
            try:
                pid = int([a for a in args if not a.startswith("-")][0])
            except (ValueError, IndexError):
                print("kill: invalid process ID")
                return
                
            if force:
                print(f"Forcefully killing process {pid}...")
            else:
                print(f"Terminating process {pid}...")
                
            success = SystemMonitor.kill_process(pid, force)
            
            if success:
                print(f"Process {pid} {('killed' if force else 'terminated')} successfully")
            else:
                print(f"Failed to {('kill' if force else 'terminate')} process {pid}")
                
        except Exception as e:
            logger.error(f"Error in kill command: {e}")
            print(f"kill: {str(e)}")
    
    def do_cp(self, arg):
        """Copy files or directories"""
        try:
            args = shlex.split(arg)
            if len(args) < 2:
                print("cp: missing file operand")
                return

            recursive = "-r" in args or "-R" in args
            args = [a for a in args if not a.startswith("-")]

            source = args[0]
            dest = args[1]

            self.fs.copy(source, dest, recursive=recursive)
            logger.info(f"Copied {source} to {dest}")

        except Exception as e:
            logger.error(f"Error in cp command: {e}")
            print(f"cp: {str(e)}")

    def do_mv(self, arg):
        """Move/rename files or directories"""
        try:
            args = shlex.split(arg)
            if len(args) < 2:
                print("mv: missing file operand")
                return

            source = args[0]
            dest = args[1]

            self.fs.move(source, dest)
            logger.info(f"Moved {source} to {dest}")

        except Exception as e:
            logger.error(f"Error in mv command: {e}")
            print(f"mv: {str(e)}")

    def do_chmod(self, arg):
        """Change file permissions"""
        try:
            args = shlex.split(arg)
            if len(args) < 2:
                print("chmod: missing operand")
                return

            mode = args[0]
            path = args[1]

            # Convert mode from octal string to integer
            mode_int = int(mode, 8)
            self.fs.chmod(path, mode_int)
            logger.info(f"Changed mode of {path} to {mode}")

        except Exception as e:
            logger.error(f"Error in chmod command: {e}")
            print(f"chmod: {str(e)}")

    def do_grep(self, arg):
        """Search file patterns with highlighting"""
        try:
            args = shlex.split(arg)
            if len(args) < 2:
                print("grep: missing pattern or file operand")
                return

            pattern = args[0]
            paths = [a for a in args if not a.startswith("-")]
            paths = paths[1:]  # Remove pattern from paths
            ignore_case = "-i" in args

            for path in paths:
                try:
                    content = self.fs.read_file(path)
                    lines = content.split('\n')
                    for i, line in enumerate(lines, 1):
                        if (ignore_case and pattern.lower()
                                in line.lower()) or pattern in line:
                            if RICH_AVAILABLE and self.console:
                                highlighted = line.replace(
                                    pattern, f"[red]{pattern}[/red]")
                                self.console.print(
                                    f"{path}:{i}: {highlighted}")
                            else:
                                print(f"{path}:{i}: {line}")
                except Exception as e:
                    print(f"grep: {path}: {str(e)}")

        except Exception as e:
            logger.error(f"Error in grep command: {e}")
            print(f"grep: {str(e)}")

    def do_find(self, arg):
        """Search files with advanced criteria"""
        try:
            args = shlex.split(arg)
            if not args:
                path = "."
                pattern = "*"
            else:
                path = args[0]
                pattern = args[1] if len(args) > 1 else "*"

            type_filter = None
            if "-type" in args:
                type_idx = args.index("-type") + 1
                if type_idx < len(args):
                    type_filter = args[type_idx]

            name_filter = None
            if "-name" in args:
                name_idx = args.index("-name") + 1
                if name_idx < len(args):
                    name_filter = args[name_idx]

            results = self.fs.find(path,
                                   pattern=pattern,
                                   file_type=type_filter,
                                   name=name_filter)

            if RICH_AVAILABLE and self.console:
                table = Table(title="Find Results")
                table.add_column("Path")
                table.add_column("Type")
                table.add_column("Size")

                for result in results:
                    table.add_row(result['path'], result['type'],
                                  str(result['size']))
                self.console.print(table)
            else:
                for result in results:
                    print(
                        f"{result['path']} ({result['type']}, {result['size']} bytes)"
                    )

        except Exception as e:
            logger.error(f"Error in find command: {e}")
            print(f"find: {str(e)}")

    def do_touch(self, arg):
        """Create or update file timestamps"""
        try:
            args = shlex.split(arg)
            if not args:
                print("touch: missing file operand")
                return

            for path in args:
                self.fs.touch(path)
                logger.info(f"Updated timestamp: {path}")

        except Exception as e:
            logger.error(f"Error in touch command: {e}")
            print(f"touch: {str(e)}")

    def do_tree(self, arg):
        """Display directory structure"""
        try:
            path = arg.strip() or "."
            tree_data = self.fs.get_directory_tree(path)

            if RICH_AVAILABLE and self.console:

                def print_tree(node, prefix=""):
                    self.console.print(f"{prefix}├── {node['name']}")
                    for child in node.get('children', []):
                        print_tree(child, prefix + "│   ")
            else:

                def print_tree(node, prefix=""):
                    print(f"{prefix}├── {node['name']}")
                    for child in node.get('children', []):
                        print_tree(child, prefix + "│   ")

            print_tree(tree_data)

        except Exception as e:
            logger.error(f"Error in tree command: {e}")
            print(f"tree: {str(e)}")

    def do_hostname(self, arg):
        """Show/set system hostname"""
        try:
            if not arg:
                print("kos")
                return

            if not self.us.can_sudo(self.us.current_user):
                print("hostname: Permission denied")
                return

            # This is a simulated hostname change since we're in a virtual environment
            print(f"Hostname changed to: {arg}")
            logger.info(f"Hostname changed to {arg}")

        except Exception as e:
            logger.error(f"Error in hostname command: {e}")
            print(f"hostname: {str(e)}")

    def do_userdel(self, arg):
        """Delete user"""
        try:
            if not arg:
                print("userdel: missing operand")
                return

            if not self.us.can_sudo(self.us.current_user):
                print("userdel: Permission denied")
                return

            username = arg.strip()
            if self.us.delete_user(username):
                print(f"User {username} deleted successfully")
            else:
                print(f"Failed to delete user {username}")

        except Exception as e:
            logger.error(f"Error in userdel command: {e}")
            print(f"userdel: {str(e)}")

    def do_passwd(self, arg):
        """Change password"""
        try:
            username = arg.strip() or self.us.current_user

            if username != self.us.current_user and not self.us.can_kudo(
                    self.us.current_user):
                print("passwd: Permission denied")
                return

            new_password = input("New password: ")
            if self.us.change_password(username, new_password):
                print("Password changed successfully")
            else:
                print("Failed to change password")

        except Exception as e:
            logger.error(f"Error in passwd command: {e}")
            print(f"passwd: {str(e)}")

    def do_groups(self, arg):
        """Show user groups"""
        try:
            username = arg.strip() or self.us.current_user
            user_info = self.us.get_user_info(username)

            if RICH_AVAILABLE and self.console:
                table = Table(title=f"Groups for {username}")
                table.add_column("Groups")
                table.add_row(", ".join(user_info["groups"]))
                self.console.print(table)
            else:
                print(
                    f"Groups for {username}: {', '.join(user_info['groups'])}")

        except Exception as e:
            logger.error(f"Error in groups command: {e}")
            print(f"groups: {str(e)}")

    def do_kudo(self, arg):
        """Execute with elevated privileges"""
        try:
            if not arg:
                print("kudo: missing operand")
                return

            if not self.us.can_sudo(self.us.current_user):
                print("kudo: Permission denied")
                return

            # Execute the command with elevated privileges
            self.onecmd(arg)
            logger.info(f"Executed command with kudo: {arg}")

        except Exception as e:
            logger.error(f"Error in kudo command: {e}")
            print(f"kudo: {str(e)}")

    def do_intro(self, arg):
        """Display system introduction message"""
        print(self._get_intro())

    def do_uname(self, arg):
        """Print system information"""
        try:
            if RICH_AVAILABLE and self.console:
                table = Table(title="System Information")
                table.add_column("Component")
                table.add_column("Value")

                table.add_row("Operating System", "KOS")
                table.add_row("Version", __version__)
                table.add_row("Machine", "Python Virtual System")
                table.add_row("Processor", "Virtual CPU")
                table.add_row("Platform", sys.platform)

                self.console.print(table)
            else:
                print(f"KOS version {__version__} on {sys.platform}")

        except Exception as e:
            logger.error(f"Error in uname command: {e}")
            print(f"uname: {str(e)}")

    def do_uptime(self, arg):
        """Show system uptime"""
        try:
            boot_time = psutil.boot_time()
            uptime = time.time() - boot_time
            days = int(uptime // (24 * 3600))
            hours = int((uptime % (24 * 3600)) // 3600)
            minutes = int((uptime % 3600) // 60)

            if RICH_AVAILABLE and self.console:
                self.console.print(
                    f"Uptime: {days} days, {hours} hours, {minutes} minutes")
            else:
                print(f"Uptime: {days} days, {hours} hours, {minutes} minutes")

        except Exception as e:
            logger.error(f"Error in uptime command: {e}")
            print(f"uptime: {str(e)}")

    def do_date(self, arg):
        """Display/set system date"""
        try:
            if not arg:
                current_time = datetime.now()
                print(current_time.strftime("%Y-%m-%d %H:%M:%S"))
                return

            if not self.us.can_sudo(self.us.current_user):
                print("date: Permission denied")
                return

            # This is a simulated date change since we're in a virtual environment
            print(f"Date would be set to: {arg}")
            logger.info(f"Date change requested to {arg}")

        except Exception as e:
            logger.error(f"Error in date command: {e}")
            print(f"date: {str(e)}")

    def do_free(self, arg):
        """Display memory usage"""
        try:
            resources = self.process_mgr.get_system_resources()
            memory = resources['memory']['virtual']
            swap = resources['memory']['swap']

            if RICH_AVAILABLE and self.console:
                table = Table(title="Memory Information")
                table.add_column("Type")
                table.add_column("Total")
                table.add_column("Used")
                table.add_column("Free")
                table.add_column("Available")

                def format_bytes(bytes):
                    return f"{bytes / (1024*1024):.1f}M"

                table.add_row("Memory", format_bytes(memory['total']),
                              format_bytes(memory['used']),
                              format_bytes(memory['free']),
                              format_bytes(memory['available']))
                table.add_row("Swap", format_bytes(swap['total']),
                              format_bytes(swap['used']),
                              format_bytes(swap['free']), "-")
                self.console.print(table)
            else:
                print("Memory:")
                print(f"  Total: {memory['total'] / (1024*1024):.1f}M")
                print(f"  Used: {memory['used'] / (1024*1024):.1f}M")
                print(f"  Free: {memory['free'] / (1024*1024):.1f}M")
                print(f"  Available: {memory['available'] / (1024*1024):.1f}M")
                print("\nSwap:")
                print(f"  Total: {swap['total'] / (1024*1024):.1f}M")
                print(f"  Used: {swap['used'] / (1024*1024):.1f}M")
                print(f"  Free: {swap['free'] / (1024*1024):.1f}M")

        except Exception as e:
            logger.error(f"Error in free command: {e}")
            print(f"free: {str(e)}")

    def do_sysinfo(self, arg):
        """Show system statistics"""
        try:
            resources = self.process_mgr.get_system_resources()

            if RICH_AVAILABLE and self.console:
                table = Table(title="System Statistics")
                table.add_column("Component")
                table.add_column("Statistics")

                # CPU Information
                cpu_info = [
                    f"Usage: {resources['cpu']['percent']}%",
                    f"Cores: {resources['cpu']['count']}"
                ]
                if resources['cpu']['freq']:
                    cpu_info.append(
                        f"Frequency: {resources['cpu']['freq']['current']}MHz")
                table.add_row("CPU", "\n".join(cpu_info))

                # Memory Information
                mem = resources['memory']['virtual']
                table.add_row(
                    "Memory", f"Total: {mem['total']/1024/1024:.1f}MB\n"
                    f"Used: {mem['used']/1024/1024:.1f}MB ({mem['percent']}%)\n"
                    f"Available: {mem['available']/1024/1024:.1f}MB")

                # Disk Information
                disk = resources['disk']['usage']
                table.add_row(
                    "Disk", f"Total: {disk['total']/1024/1024:.1f}MB\n"
                    f"Used: {disk['used']/1024/1024:.1f}MB ({disk['percent']}%)\n"
                    f"Free: {disk['free']/1024/1024:.1f}MB")

                # Network Information
                if resources['network']['io']:
                    net = resources['network']['io']
                    table.add_row(
                        "Network", f"Sent: {net['bytes_sent']/1024:.1f}KB\n"
                        f"Received: {net['bytes_recv']/1024:.1f}KB\n"
                        f"Connections: {resources['network']['connections']}")

                self.console.print(table)
            else:
                print("\nSystem Statistics:")
                print(f"CPU Usage: {resources['cpu']['percent']}%")
                print(
                    f"Memory Used: {resources['memory']['virtual']['percent']}%"
                )
                print(f"Disk Used: {resources['disk']['usage']['percent']}%")
                if resources['network']['io']:
                    print(
                        f"Network Connections: {resources['network']['connections']}"
                    )

        except Exception as e:
            logger.error(f"Error in sysinfo command: {e}")
            print(f"sysinfo: {str(e)}")
    
    def do_head(self, arg):
        """Output the first part of files
        
        Usage: head [OPTION]... [FILE]...
        Print the first 10 lines of each FILE to standard output.
        
        Options:
          -n, --lines=N    Print the first N lines instead of the first 10
          -q, --quiet      Never print headers giving file names
          -v, --verbose    Always print headers giving file names
        
        With more than one FILE, precede each with a header giving the file name.
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("head: missing file operand")
                print("Try 'head --help' for more information.")
                return
                
            # Parse options
            lines = 10  # Default number of lines
            quiet = False
            verbose = False
            files = []
            
            i = 0
            while i < len(args):
                if args[i] in ['-h', '--help']:
                    print(self.do_head.__doc__)
                    return
                elif args[i] in ['-n', '--lines']:
                    if i + 1 < len(args):
                        try:
                            lines = int(args[i + 1])
                            i += 2
                            continue
                        except ValueError:
                            print(f"head: invalid number of lines: '{args[i + 1]}'")
                            return
                    else:
                        print("head: option requires an argument -- 'n'")
                        return
                elif args[i].startswith('--lines='):
                    try:
                        lines = int(args[i].split('=')[1])
                    except (ValueError, IndexError):
                        print(f"head: invalid number of lines: '{args[i].split('=')[1]}'")
                        return
                elif args[i] in ['-q', '--quiet']:
                    quiet = True
                elif args[i] in ['-v', '--verbose']:
                    verbose = True
                else:
                    files.append(args[i])
                i += 1
                
            if not files:
                print("head: missing file operand")
                return
                
            # Process each file
            show_headers = (len(files) > 1 or verbose) and not quiet
            
            for idx, filename in enumerate(files):
                # Resolve path
                path = os.path.join(self.fs.cwd, filename) if not os.path.isabs(filename) else filename
                
                # Check if file exists
                if not self.fs.exists(path):
                    print(f"head: cannot open '{filename}' for reading: No such file or directory")
                    continue
                    
                # Check if it's a directory
                if self.fs.is_dir(path):
                    print(f"head: error reading '{filename}': Is a directory")
                    continue
                    
                # Read file content
                try:
                    content = self.fs.read_file(path)
                    file_lines = content.split('\n')
                    
                    # Display header if needed
                    if show_headers:
                        if idx > 0:
                            print("")
                        print(f"==> {filename} <==")
                    
                    # Display the first n lines
                    for i in range(min(lines, len(file_lines))):
                        print(file_lines[i])
                        
                except Exception as e:
                    print(f"head: error reading '{filename}': {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error in head command: {e}")
            print(f"head: {str(e)}")
    
    def do_tail(self, arg):
        """Output the last part of files
        
        Usage: tail [OPTION]... [FILE]...
        Print the last 10 lines of each FILE to standard output.
        
        Options:
          -n, --lines=N    Print the last N lines instead of the last 10
          -f, --follow     Output appended data as the file grows
          -q, --quiet      Never print headers giving file names
          -v, --verbose    Always print headers giving file names
        
        With more than one FILE, precede each with a header giving the file name.
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("tail: missing file operand")
                print("Try 'tail --help' for more information.")
                return
                
            # Parse options
            lines = 10  # Default number of lines
            follow = False
            quiet = False
            verbose = False
            files = []
            
            i = 0
            while i < len(args):
                if args[i] in ['-h', '--help']:
                    print(self.do_tail.__doc__)
                    return
                elif args[i] in ['-n', '--lines']:
                    if i + 1 < len(args):
                        try:
                            lines = int(args[i + 1])
                            i += 2
                            continue
                        except ValueError:
                            print(f"tail: invalid number of lines: '{args[i + 1]}'")
                            return
                    else:
                        print("tail: option requires an argument -- 'n'")
                        return
                elif args[i].startswith('--lines='):
                    try:
                        lines = int(args[i].split('=')[1])
                    except (ValueError, IndexError):
                        print(f"tail: invalid number of lines: '{args[i].split('=')[1]}'")
                        return
                elif args[i] in ['-f', '--follow']:
                    follow = True
                elif args[i] in ['-q', '--quiet']:
                    quiet = True
                elif args[i] in ['-v', '--verbose']:
                    verbose = True
                else:
                    files.append(args[i])
                i += 1
                
            if not files:
                print("tail: missing file operand")
                return
                
            # Process each file
            show_headers = (len(files) > 1 or verbose) and not quiet
            
            for idx, filename in enumerate(files):
                # Resolve path
                path = os.path.join(self.fs.cwd, filename) if not os.path.isabs(filename) else filename
                
                # Check if file exists
                if not self.fs.exists(path):
                    print(f"tail: cannot open '{filename}' for reading: No such file or directory")
                    continue
                    
                # Check if it's a directory
                if self.fs.is_dir(path):
                    print(f"tail: error reading '{filename}': Is a directory")
                    continue
                    
                # Read file content
                try:
                    content = self.fs.read_file(path)
                    file_lines = content.split('\n')
                    
                    # Display header if needed
                    if show_headers:
                        if idx > 0:
                            print("")
                        print(f"==> {filename} <==")
                    
                    # Display the last n lines
                    start_line = max(0, len(file_lines) - lines)
                    for i in range(start_line, len(file_lines)):
                        print(file_lines[i])
                    
                    # Follow mode (not fully implemented, would need file watching)
                    if follow:
                        print(f"\ntail: --follow not fully implemented for {filename}")
                        print("Press Ctrl+C to exit follow mode")
                        
                        # Simple implementation of follow - just wait for user to cancel
                        try:
                            while True:
                                # Re-read the file every second
                                time.sleep(1)
                                new_content = self.fs.read_file(path)
                                new_lines = new_content.split('\n')
                                
                                # Check if there are new lines
                                if len(new_lines) > len(file_lines):
                                    # Display only the new lines
                                    for i in range(len(file_lines), len(new_lines)):
                                        print(new_lines[i])
                                    file_lines = new_lines
                        except KeyboardInterrupt:
                            print("\nFollow mode terminated.")
                        
                except Exception as e:
                    print(f"tail: error reading '{filename}': {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error in tail command: {e}")
            print(f"tail: {str(e)}")
    
    def do_wc(self, arg):
        """Print newline, word, and byte counts for each file
        
        Usage: wc [OPTION]... [FILE]...
        Print newline, word, and byte counts for each FILE, and a total line if
        more than one FILE is specified.
        
        Options:
          -c, --bytes       Print the byte counts
          -m, --chars       Print the character counts
          -l, --lines       Print the newline counts
          -w, --words       Print the word counts
        
        If no FILE is specified, or when FILE is -, read standard input.
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("wc: missing file operand")
                print("Try 'wc --help' for more information.")
                return
                
            # Parse options
            count_bytes = True   # By default, show all counts
            count_chars = False  # Characters only shown when explicitly requested
            count_lines = True
            count_words = True
            files = []
            
            # Check for explicit options
            explicit_options = False
            
            i = 0
            while i < len(args):
                if args[i] in ['-h', '--help']:
                    print(self.do_wc.__doc__)
                    return
                elif args[i] in ['-c', '--bytes']:
                    count_bytes = True
                    explicit_options = True
                elif args[i] in ['-m', '--chars']:
                    count_chars = True
                    explicit_options = True
                elif args[i] in ['-l', '--lines']:
                    count_lines = True
                    explicit_options = True
                elif args[i] in ['-w', '--words']:
                    count_words = True
                    explicit_options = True
                else:
                    files.append(args[i])
                i += 1
                
            # If explicit options are given, only show those requested
            if explicit_options:
                count_bytes = '-c' in args or '--bytes' in args
                count_lines = '-l' in args or '--lines' in args
                count_words = '-w' in args or '--words' in args
                # Characters are only shown when explicitly requested
                
            if not files:
                print("wc: missing file operand")
                return
                
            # Process each file
            total_lines = 0
            total_words = 0
            total_bytes = 0
            total_chars = 0
            
            # Format for output
            line_width = 7  # Default width for count columns
            
            results = []
            
            for filename in files:
                # Resolve path
                path = os.path.join(self.fs.cwd, filename) if not os.path.isabs(filename) else filename
                
                # Check if file exists
                if not self.fs.exists(path):
                    print(f"wc: cannot open '{filename}' for reading: No such file or directory")
                    continue
                    
                # Check if it's a directory
                if self.fs.is_dir(path):
                    print(f"wc: {filename}: Is a directory")
                    continue
                    
                # Read file content
                try:
                    content = self.fs.read_file(path)
                    
                    # Count metrics
                    lines = content.count('\n') + (1 if content and not content.endswith('\n') else 0)
                    words = len(content.split())
                    bytes_count = len(content.encode('utf-8'))  # Get actual byte count
                    chars_count = len(content)  # Character count
                    
                    # Add to totals
                    total_lines += lines
                    total_words += words
                    total_bytes += bytes_count
                    total_chars += chars_count
                    
                    # Store result
                    results.append((filename, lines, words, bytes_count, chars_count))
                        
                except Exception as e:
                    print(f"wc: {filename}: {str(e)}")
                    
            # Display results with proper formatting
            for filename, lines, words, bytes_count, chars_count in results:
                output_parts = []
                
                if count_lines:
                    output_parts.append(f"{lines:{line_width}}")
                if count_words:
                    output_parts.append(f"{words:{line_width}}")
                if count_bytes:
                    output_parts.append(f"{bytes_count:{line_width}}")
                if count_chars:
                    output_parts.append(f"{chars_count:{line_width}}")
                    
                output_parts.append(filename)
                print(" ".join(output_parts))
                
            # Print totals if more than one file
            if len(results) > 1:
                output_parts = []
                
                if count_lines:
                    output_parts.append(f"{total_lines:{line_width}}")
                if count_words:
                    output_parts.append(f"{total_words:{line_width}}")
                if count_bytes:
                    output_parts.append(f"{total_bytes:{line_width}}")
                if count_chars:
                    output_parts.append(f"{total_chars:{line_width}}")
                    
                output_parts.append("total")
                print(" ".join(output_parts))
                
        except Exception as e:
            logger.error(f"Error in wc command: {e}")
            print(f"wc: {str(e)}")
            
    def do_sort(self, arg):
        """Sort lines of text files
        
        Usage: sort [OPTION]... [FILE]...
        Write sorted concatenation of all FILE(s) to standard output.
        
        Options:
          -b, --ignore-leading-blanks  Ignore leading blanks
          -f, --ignore-case            Fold lower case to upper case characters
          -n, --numeric-sort           Compare according to string numerical value
          -r, --reverse                Reverse the result of comparisons
          -u, --unique                 Output only the first of an equal run
          -o, --output=FILE            Write result to FILE instead of standard output
        
        If no FILE is specified, read standard input.
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("sort: missing file operand")
                print("Try 'sort --help' for more information.")
                return
                
            # Parse options
            ignore_blanks = False
            ignore_case = False
            numeric_sort = False
            reverse_sort = False
            unique_lines = False
            output_file = None
            files = []
            
            i = 0
            while i < len(args):
                if args[i] in ['-h', '--help']:
                    print(self.do_sort.__doc__)
                    return
                elif args[i] in ['-b', '--ignore-leading-blanks']:
                    ignore_blanks = True
                elif args[i] in ['-f', '--ignore-case']:
                    ignore_case = True
                elif args[i] in ['-n', '--numeric-sort']:
                    numeric_sort = True
                elif args[i] in ['-r', '--reverse']:
                    reverse_sort = True
                elif args[i] in ['-u', '--unique']:
                    unique_lines = True
                elif args[i] in ['-o', '--output']:
                    if i + 1 < len(args):
                        output_file = args[i + 1]
                        i += 2
                        continue
                    else:
                        print("sort: option requires an argument -- 'o'")
                        return
                elif args[i].startswith('--output='):
                    try:
                        output_file = args[i].split('=')[1]
                    except IndexError:
                        print("sort: option '--output=' requires an argument")
                        return
                else:
                    files.append(args[i])
                i += 1
                
            # Collect all lines from all files
            all_lines = []
            
            for filename in files:
                # Resolve path
                path = os.path.join(self.fs.cwd, filename) if not os.path.isabs(filename) else filename
                
                # Check if file exists
                if not self.fs.exists(path):
                    print(f"sort: cannot open '{filename}' for reading: No such file or directory")
                    continue
                    
                # Check if it's a directory
                if self.fs.is_dir(path):
                    print(f"sort: {filename}: Is a directory")
                    continue
                    
                # Read file content
                try:
                    content = self.fs.read_file(path)
                    file_lines = content.split('\n')
                    all_lines.extend(file_lines)
                        
                except Exception as e:
                    print(f"sort: {filename}: {str(e)}")
            
            # Define sort key based on options
            def get_sort_key(line):
                if ignore_blanks:
                    line = line.lstrip()
                if ignore_case:
                    line = line.lower()
                if numeric_sort:
                    # Try to extract numeric prefix for sorting
                    match = re.match(r'^\s*([+-]?\d+(?:\.\d+)?)', line)
                    if match:
                        try:
                            return float(match.group(1)), line
                        except ValueError:
                            pass
                    return 0, line
                return line
            
            # Sort the lines
            sorted_lines = sorted(all_lines, key=get_sort_key, reverse=reverse_sort)
            
            # Apply uniqueness if requested
            if unique_lines:
                unique_sorted_lines = []
                prev_line = None
                for line in sorted_lines:
                    if line != prev_line:
                        unique_sorted_lines.append(line)
                        prev_line = line
                sorted_lines = unique_sorted_lines
            
            # Output the result
            output = '\n'.join(sorted_lines)
            
            if output_file:
                # Resolve output path
                output_path = os.path.join(self.fs.cwd, output_file) if not os.path.isabs(output_file) else output_file
                
                # Check if parent directory exists
                parent_dir = os.path.dirname(output_path)
                if parent_dir and not self.fs.exists(parent_dir):
                    print(f"sort: cannot open '{output_file}' for writing: No such directory")
                    return
                    
                # Write to the output file
                try:
                    self.fs.write_file(output_path, output)
                except Exception as e:
                    print(f"sort: cannot write to '{output_file}': {str(e)}")
            else:
                # Print to standard output
                print(output)
                
        except Exception as e:
            logger.error(f"Error in sort command: {e}")
            print(f"sort: {str(e)}")
            
    def do_grep(self, arg):
        """Print lines matching a pattern
        
        Usage: grep [OPTION]... PATTERN [FILE]...
        Search for PATTERN in each FILE or standard input.
        PATTERN is a regular expression by default.
        
        Options:
          -i, --ignore-case         Ignore case distinctions in patterns and data
          -v, --invert-match        Select non-matching lines
          -c, --count              Print only a count of matching lines per FILE
          -n, --line-number        Print line number with output lines
          -H, --with-filename      Print the file name for each match
          -h, --no-filename        Suppress the file name prefix on output
          -r, --recursive          Read all files under each directory, recursively
          -E, --extended-regexp    PATTERN is an extended regular expression
          -F, --fixed-strings      PATTERN is a set of newline-separated strings
        
        Examples:
          grep -i 'hello world' menu.h main.c     # Search for "hello world" in menu.h and main.c
          grep -r 'function' --include="*.py" .   # Search for "function" in all Python files
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("grep: missing pattern operand")
                print("Try 'grep --help' for more information.")
                return
                
            # Parse options
            ignore_case = False
            invert_match = False
            count_only = False
            line_numbers = False
            with_filename = False
            no_filename = False
            recursive = False
            extended_regexp = False
            fixed_strings = False
            pattern = None
            files = []
            
            i = 0
            while i < len(args):
                if args[i] in ['-h', '--help']:
                    print(self.do_grep.__doc__)
                    return
                elif args[i] in ['-i', '--ignore-case']:
                    ignore_case = True
                elif args[i] in ['-v', '--invert-match']:
                    invert_match = True
                elif args[i] in ['-c', '--count']:
                    count_only = True
                elif args[i] in ['-n', '--line-number']:
                    line_numbers = True
                elif args[i] in ['-H', '--with-filename']:
                    with_filename = True
                    no_filename = False
                elif args[i] in ['-h', '--no-filename']:
                    no_filename = True
                    with_filename = False
                elif args[i] in ['-r', '--recursive']:
                    recursive = True
                elif args[i] in ['-E', '--extended-regexp']:
                    extended_regexp = True
                elif args[i] in ['-F', '--fixed-strings']:
                    fixed_strings = True
                elif pattern is None and not args[i].startswith('-'):
                    # First non-option argument is the pattern
                    pattern = args[i]
                else:
                    # All other non-option arguments are file names
                    files.append(args[i])
                i += 1
                
            if pattern is None:
                print("grep: missing pattern operand")
                return
                
            if not files:
                print("grep: missing file operand")
                return
                
            # Determine if we should show filenames in output
            show_filename = (len(files) > 1 or with_filename) and not no_filename
            
            # Process files
            total_matches = 0
            processed_files = 0
            
            # Compile the pattern based on options
            if fixed_strings:
                # For fixed strings, escape the pattern to match it literally
                pattern_obj = re.compile(re.escape(pattern), re.IGNORECASE if ignore_case else 0)
            else:
                # For regular expressions
                try:
                    if ignore_case:
                        pattern_obj = re.compile(pattern, re.IGNORECASE)
                    else:
                        pattern_obj = re.compile(pattern)
                except re.error as e:
                    print(f"grep: invalid regular expression: {str(e)}")
                    return
                    
            # Function to process a single file
            def process_file(filename, path):
                nonlocal total_matches, processed_files
                
                try:
                    if self.fs.is_dir(path):
                        if recursive:
                            # Process directory recursively
                            for child in self.fs.list_dir(path):
                                child_path = os.path.join(path, child)
                                child_name = os.path.join(filename, child)
                                process_file(child_name, child_path)
                        else:
                            print(f"grep: {filename}: Is a directory")
                        return
                        
                    # Read and process the file
                    content = self.fs.read_file(path)
                    lines = content.split('\n')
                    matches = 0
                    
                    for line_num, line in enumerate(lines, 1):
                        is_match = bool(pattern_obj.search(line))
                        if invert_match:
                            is_match = not is_match
                            
                        if is_match:
                            matches += 1
                            if not count_only:
                                output_parts = []
                                if show_filename:
                                    output_parts.append(f"{filename}:")
                                if line_numbers:
                                    output_parts.append(f"{line_num}:")
                                output_parts.append(line)
                                print("".join(output_parts))
                                
                    if count_only:
                        if show_filename:
                            print(f"{filename}:{matches}")
                        else:
                            print(matches)
                            
                    total_matches += matches
                    processed_files += 1
                    
                except Exception as e:
                    print(f"grep: {filename}: {str(e)}")
                    
            # Process each file
            for filename in files:
                # Resolve path
                path = os.path.join(self.fs.cwd, filename) if not os.path.isabs(filename) else filename
                
                # Check if file exists
                if not self.fs.exists(path):
                    print(f"grep: {filename}: No such file or directory")
                    continue
                    
                process_file(filename, path)
                
            # Return status code (0 if matches were found, 1 otherwise)
            return 0 if total_matches > 0 else 1
                
        except Exception as e:
            logger.error(f"Error in grep command: {e}")
            print(f"grep: {str(e)}")
            
    def do_find(self, arg):
        """Search for files in a directory hierarchy
        
        Usage: find [PATH...] [EXPRESSION]
        Search for files in the specified PATHs (default is current directory) based on the given expression.
        
        Options:
          -name PATTERN       File name matches PATTERN (wildcard * and ? supported)
          -type TYPE          File is of type TYPE (f: regular file, d: directory)
          -size N[cwbkMG]     File uses N units of space (c: bytes, w: 2-byte words, b: 512-byte blocks,
                              k: kilobytes, M: megabytes, G: gigabytes)
          -empty              File is empty and is either a regular file or a directory
          -executable         File is executable
          -readable           File is readable
          -writable           File is writable
          -maxdepth LEVELS    Descend at most LEVELS of directories below the start points
          -mindepth LEVELS    Do not apply any tests or actions at levels less than LEVELS
        
        Examples:
          find . -name "*.txt"         # Find all .txt files in current directory and subdirectories
          find /home -type d -empty    # Find all empty directories under /home
        """
        try:
            args = shlex.split(arg)
            if not args:
                # Default to current directory if no path specified
                paths = ['.']
                expressions = []
            else:
                # Parse arguments to separate paths from expressions
                paths = []
                expressions = []
                i = 0
                while i < len(args):
                    if args[i] in ['-h', '--help']:
                        print(self.do_find.__doc__)
                        return
                    elif args[i].startswith('-'):
                        # This is the start of expressions
                        expressions = args[i:]
                        break
                    else:
                        # This is a path
                        paths.append(args[i])
                    i += 1
                    
                # If no paths were specified, use current directory
                if not paths:
                    paths = ['.']
                    
            # Parse expressions
            name_pattern = None
            file_type = None
            size_expr = None
            is_empty = False
            is_executable = None
            is_readable = None
            is_writable = None
            max_depth = float('inf')
            min_depth = 0
            
            i = 0
            while i < len(expressions):
                if expressions[i] == '-name':
                    if i + 1 < len(expressions):
                        name_pattern = expressions[i + 1]
                        # Convert glob pattern to regex
                        name_pattern = name_pattern.replace('.', '\\.')
                        name_pattern = name_pattern.replace('*', '.*')
                        name_pattern = name_pattern.replace('?', '.')
                        name_pattern = f'^{name_pattern}$'
                        i += 2
                    else:
                        print("find: missing argument to '-name'")
                        return
                elif expressions[i] == '-type':
                    if i + 1 < len(expressions):
                        file_type = expressions[i + 1]
                        if file_type not in ['f', 'd']:
                            print(f"find: Unknown argument to -type: {file_type}")
                            print("Valid arguments are 'f' (regular file) and 'd' (directory)")
                            return
                        i += 2
                    else:
                        print("find: missing argument to '-type'")
                        return
                elif expressions[i] == '-size':
                    if i + 1 < len(expressions):
                        size_expr = expressions[i + 1]
                        # Size parsing will be done during evaluation
                        i += 2
                    else:
                        print("find: missing argument to '-size'")
                        return
                elif expressions[i] == '-empty':
                    is_empty = True
                    i += 1
                elif expressions[i] == '-executable':
                    is_executable = True
                    i += 1
                elif expressions[i] == '-readable':
                    is_readable = True
                    i += 1
                elif expressions[i] == '-writable':
                    is_writable = True
                    i += 1
                elif expressions[i] == '-maxdepth':
                    if i + 1 < len(expressions):
                        try:
                            max_depth = int(expressions[i + 1])
                            if max_depth < 0:
                                print("find: Invalid argument to -maxdepth: must be non-negative")
                                return
                            i += 2
                        except ValueError:
                            print(f"find: Invalid argument to -maxdepth: {expressions[i + 1]}")
                            return
                    else:
                        print("find: missing argument to '-maxdepth'")
                        return
                elif expressions[i] == '-mindepth':
                    if i + 1 < len(expressions):
                        try:
                            min_depth = int(expressions[i + 1])
                            if min_depth < 0:
                                print("find: Invalid argument to -mindepth: must be non-negative")
                                return
                            i += 2
                        except ValueError:
                            print(f"find: Invalid argument to -mindepth: {expressions[i + 1]}")
                            return
                    else:
                        print("find: missing argument to '-mindepth'")
                        return
                else:
                    print(f"find: unknown predicate '{expressions[i]}'")
                    i += 1
                    
            # Compile name pattern regex if provided
            name_regex = re.compile(name_pattern) if name_pattern else None
            
            # Parse size expression if provided
            size_value = None
            size_unit = None
            if size_expr:
                match = re.match(r'^([+-]?)([0-9]+)([cwbkMG]?)$', size_expr)
                if match:
                    sign, value, unit = match.groups()
                    try:
                        size_value = int(value)
                        if sign == '-':
                            size_value = -size_value
                        size_unit = unit if unit else 'b'  # Default to 512-byte blocks
                    except ValueError:
                        print(f"find: Invalid size value: {size_expr}")
                        return
                else:
                    print(f"find: Invalid size format: {size_expr}")
                    return
                    
            # Function to process a directory recursively
            def process_directory(path, rel_path, depth=0):
                if depth > max_depth:
                    return
                    
                try:
                    # List directory contents
                    contents = self.fs.list_dir(path)
                    
                    # Process each item
                    for item in contents:
                        item_path = os.path.join(path, item)
                        item_rel_path = os.path.join(rel_path, item) if rel_path != '.' else item
                        
                        # Check if the item is a directory
                        is_dir = self.fs.is_dir(item_path)
                        
                        # Apply filters only if we're at or above min_depth
                        if depth >= min_depth:
                            # Check file type
                            if file_type:
                                if file_type == 'f' and is_dir:
                                    continue
                                if file_type == 'd' and not is_dir:
                                    continue
                                    
                            # Check name pattern
                            if name_regex and not name_regex.match(item):
                                continue
                                
                            # Check emptiness
                            if is_empty:
                                if is_dir:
                                    # For directories, check if it has any contents
                                    if self.fs.list_dir(item_path):
                                        continue
                                else:
                                    # For files, check if it has zero size
                                    if len(self.fs.read_file(item_path)) > 0:
                                        continue
                                        
                            # Check size if specified
                            if size_value is not None:
                                item_size = len(self.fs.read_file(item_path)) if not is_dir else 0
                                
                                # Convert size based on unit
                                if size_unit == 'c':
                                    # Bytes (no conversion needed)
                                    pass
                                elif size_unit == 'w':
                                    # 2-byte words
                                    item_size = item_size // 2
                                elif size_unit == 'b':
                                    # 512-byte blocks
                                    item_size = (item_size + 511) // 512
                                elif size_unit == 'k':
                                    # Kilobytes
                                    item_size = (item_size + 1023) // 1024
                                elif size_unit == 'M':
                                    # Megabytes
                                    item_size = (item_size + 1048575) // 1048576
                                elif size_unit == 'G':
                                    # Gigabytes
                                    item_size = (item_size + 1073741823) // 1073741824
                                    
                                # Check if size matches the criteria
                                if size_value > 0 and item_size != size_value:
                                    continue
                                elif size_value < 0 and item_size >= -size_value:
                                    continue
                                elif size_value == 0 and item_size != 0:
                                    continue
                                    
                            # Print the matching item
                            print(item_rel_path)
                            
                        # Recursively process subdirectories
                        if is_dir and depth < max_depth:
                            process_directory(item_path, item_rel_path, depth + 1)
                            
                except Exception as e:
                    print(f"find: '{rel_path}': {str(e)}")
                    
            # Process each specified path
            for path_arg in paths:
                # Resolve path
                path = os.path.join(self.fs.cwd, path_arg) if not os.path.isabs(path_arg) else path_arg
                
                # Check if path exists
                if not self.fs.exists(path):
                    print(f"find: '{path_arg}': No such file or directory")
                    continue
                    
                # Check if it's a file or directory
                if self.fs.is_dir(path):
                    # If it's a directory, process it recursively
                    if min_depth == 0:
                        # Print the root directory if it matches criteria
                        matches_criteria = True
                        
                        # Check file type
                        if file_type and file_type != 'd':
                            matches_criteria = False
                            
                        # Check name pattern
                        if name_regex and not name_regex.match(os.path.basename(path)):
                            matches_criteria = False
                            
                        # Check emptiness
                        if is_empty and self.fs.list_dir(path):
                            matches_criteria = False
                            
                        if matches_criteria:
                            print(path_arg)
                            
                    # Process the directory contents
                    process_directory(path, path_arg)
                else:
                    # If it's a file, check if it meets the criteria at depth 0
                    if min_depth <= 0:
                        matches_criteria = True
                        
                        # Check file type
                        if file_type and file_type != 'f':
                            matches_criteria = False
                            
                        # Check name pattern
                        if name_regex and not name_regex.match(os.path.basename(path)):
                            matches_criteria = False
                            
                        # Check emptiness
                        if is_empty and len(self.fs.read_file(path)) > 0:
                            matches_criteria = False
                            
                        # Check size if specified
                        if size_value is not None:
                            item_size = len(self.fs.read_file(path))
                            
                            # Convert size based on unit
                            if size_unit == 'c':
                                # Bytes (no conversion needed)
                                pass
                            elif size_unit == 'w':
                                # 2-byte words
                                item_size = item_size // 2
                            elif size_unit == 'b':
                                # 512-byte blocks
                                item_size = (item_size + 511) // 512
                            elif size_unit == 'k':
                                # Kilobytes
                                item_size = (item_size + 1023) // 1024
                            elif size_unit == 'M':
                                # Megabytes
                                item_size = (item_size + 1048575) // 1048576
                            elif size_unit == 'G':
                                # Gigabytes
                                item_size = (item_size + 1073741823) // 1073741824
                                
                            # Check if size matches the criteria
                            if size_value > 0 and item_size != size_value:
                                matches_criteria = False
                            elif size_value < 0 and item_size >= -size_value:
                                matches_criteria = False
                            elif size_value == 0 and item_size != 0:
                                matches_criteria = False
                                
                        if matches_criteria:
                            print(path_arg)
                            
        except Exception as e:
            logger.error(f"Error in find command: {e}")
            print(f"find: {str(e)}")

# Compatibility alias
KaedeShell = KOSShell

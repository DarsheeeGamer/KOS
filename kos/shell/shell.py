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

logger = logging.getLogger('KOS.shell')


class KaedeShell(cmd.Cmd):
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
        self.history: List[str] = []
        self.console = Console() if RICH_AVAILABLE and Console else None
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._resource_cache = TTLCache(
            maxsize=100, ttl=1)  # Cache resource usage for 1 second
        self._load_history()
        self._setup_signal_handlers()

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
                "tree": "Display directory structure"
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
        cwd = self.fs.current_path.replace('/home/runner/workspace', '')
        if not cwd:
            cwd = "/"

        time_str = datetime.now().strftime("%H:%M")
        branch = "main"  # TODO: Implement git integration

        if self.us.current_user == "kaede":
            return f"\033[1;31m[{time_str} root@kos {cwd} ({branch})]#\033[0m "
        return f"\033[1;34m[{time_str} {self.us.current_user}@kos {cwd} ({branch})]$\033[0m "

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

    def _cleanup(self):
        """Cleanup resources before exit"""
        try:
            self.executor.shutdown(wait=False)
            self.us.save_users()
            logger.info("Shell cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

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

    def _load_history(self):
        """Load command history from file"""
        history_file = os.path.expanduser(self.HISTORY_FILE)
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r') as f:
                    for line in f:
                        cmd = line.strip()
                        if cmd:
                            self.history.append(cmd)
            except Exception as e:
                logger.warning(f"Error loading command history: {e}")

    def precmd(self, line):
        """Preprocess command line before execution"""
        if line.strip():
            self.history.append(line)
            if len(self.history) > self.MAX_HISTORY:
                self.history.pop(0)
        return line

    def postcmd(self, stop, line):
        """Save command history after execution"""
        history_file = os.path.expanduser(self.HISTORY_FILE)
        try:
            with open(history_file, 'w') as f:
                for cmd in self.history:
                    f.write(cmd + '\n')
        except Exception as e:
            logger.warning(f"Error saving command history: {e}")
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

            # Try to change directory through filesystem
            try:
                self.fs.current_path = path
                logger.debug(f"Changed directory to: {self.fs.current_path}")
                self.prompt = self._get_prompt()  # Update prompt with new path
            except FileSystemError as e:
                print(f"cd: {str(e)}")

        except Exception as e:
            logger.error(f"Error in cd command: {e}")
            print(f"cd: {str(e)}")

        except Exception as e:
            logger.error(f"Error in cd command: {e}")
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
        print("Exiting KaedeShell...")
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

            if not self.us.can_kudo(self.us.current_user):
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

            if not self.us.can_kudo(self.us.current_user):
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

            if not self.us.can_kudo(self.us.current_user):
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

            if not self.us.can_kudo(self.us.current_user):
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

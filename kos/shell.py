"""
Enhanced shell implementation with advanced features and improved performance
"""
import readline
import atexit
import os
import cmd
import shlex
import signal
import logging
import sys
import time
import psutil
import subprocess #Added import
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from cachetools import TTLCache
from difflib import get_close_matches

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

from .filesystem import FileSystem
from .process.manager import ProcessManager
from .package.manager import PackageManager
from .exceptions import KOSError, FileSystemError
from .user_system import UserSystem
from .klayer import (
    klayer_fs,
    klayer_package,
    klayer_process,
    klayer_manual,
    get_env_var
)

logger = logging.getLogger('KOS.shell')

class KaedeShell(cmd.Cmd):
    """Enhanced KOS shell with advanced features"""
    HISTORY_FILE = os.path.expanduser("~/.kos_history")
    background_jobs = {}  # Store background jobs
    MAX_HISTORY = 1000
    COMMAND_HELP_FILE = "command_help.json"

    def __init__(self, filesystem: FileSystem, package_manager: PackageManager, 
                 user_system: UserSystem, process_manager: Optional[ProcessManager] = None):
        super().__init__()
        self.fs = filesystem
        self.pm = package_manager
        self.process_mgr = process_manager
        self.us = user_system
        self.history: List[str] = []
        self.console = Console() if RICH_AVAILABLE and Console else None
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._resource_cache = TTLCache(maxsize=100, ttl=1)  # Cache resource usage for 1 second

        # Initialize readline and history
        self._setup_readline()
        self._load_history()
        self._setup_signal_handlers()

        # Get environment variables from kLayer
        self.kos_version = get_env_var("KOS_VERSION")
        self.kos_home = get_env_var("KOS_HOME", "/home")
        self.kos_root = get_env_var("KOS_ROOT", "/root")
        self.kos_path = get_env_var("KOS_PATH", "/bin:/usr/bin")
        self.kos_shell = get_env_var("KOS_SHELL", "/bin/ksh")

        # Set shell prompt and intro
        self.intro = self._get_intro()
        self.prompt = self._get_prompt()
        logger.info("Enhanced shell initialized with kLayer integration")

        self.command_categories = {
            "File Operations": ["ls", "cd", "pwd", "mkdir", "touch", "cat", "rm", "cp", "mv", "chmod", "chown", "find", "grep", "head", "tail", "wc", "sort", "uniq", "tree", "diff", "cmp"],
            "System Operations": ["whoami", "hostname", "su", "useradd", "userdel", "kudo", "uname", "uptime", "df", "free", "date", "sysinfo", "timedatectl", "lscpu", "id", "groups", "passwd"],
            "Process Management": ["ps", "top", "kill", "jobs", "fg", "nice"],
            "Package Management": ["kpm"],
            "Network Tools": ["ping", "netstat", "wget", "curl"],
            "Text Processing": ["sed", "awk", "head", "tail", "wc", "sort", "uniq", "grep", "diff"]
        }


    def _setup_readline(self):
        """Configure readline for command history and editing"""
        readline.set_completer(self.complete)
        readline.set_completer_delims(' \t\n;')
        readline.parse_and_bind('tab: complete')

        # Configure command history navigation
        readline.parse_and_bind('"\e[A": previous-history')  # Up arrow
        readline.parse_and_bind('"\e[B": next-history')      # Down arrow
        readline.parse_and_bind('"\e[C": forward-char')      # Right arrow
        readline.parse_and_bind('"\e[D": backward-char')     # Left arrow

        # Additional keybindings
        readline.parse_and_bind('"\C-p": previous-history')  # Ctrl+P
        readline.parse_and_bind('"\C-n": next-history')      # Ctrl+N
        readline.parse_and_bind('"\C-r": reverse-search-history')  # Ctrl+R
        readline.parse_and_bind('"\C-s": forward-search-history')  # Ctrl+S
        readline.parse_and_bind('"\C-a": beginning-of-line')  # Ctrl+A
        readline.parse_and_bind('"\C-e": end-of-line')        # Ctrl+E
        readline.parse_and_bind('"\C-k": kill-line')          # Ctrl+K
        readline.parse_and_bind('"\C-u": unix-line-discard')  # Ctrl+U

        # Register history save on exit
        atexit.register(self._save_history)

    def _load_history(self):
        """Load command history from file"""
        try:
            if os.path.exists(self.HISTORY_FILE):
                readline.read_history_file(self.HISTORY_FILE)
                readline.set_history_length(self.MAX_HISTORY)
                logger.debug(f"Loaded {readline.get_current_history_length()} history entries")
        except Exception as e:
            logger.warning(f"Error loading command history: {e}")

    def _save_history(self):
        """Save command history to file"""
        try:
            os.makedirs(os.path.dirname(self.HISTORY_FILE), exist_ok=True)
            readline.write_history_file(self.HISTORY_FILE)
            logger.debug("Command history saved")
        except Exception as e:
            logger.warning(f"Error saving command history: {e}")

    def precmd(self, line):
        """Process command line before execution"""
        if line.strip():
            # Add non-empty lines to history
            try:
                readline.add_history(line)
            except Exception as e:
                logger.warning(f"Error adding to history: {e}")
        return line

    def complete(self, text, state):
        """Command completion handler"""
        if state == 0:
            # Initialize completion matches
            origline = readline.get_line_buffer()
            begin = readline.get_begidx()
            end = readline.get_endidx()
            being_completed = origline[begin:end]
            words = origline.split()

            if not words:
                self.current_candidates = sorted(self.get_names())
            else:
                try:
                    if begin == 0:
                        # First word: match commands
                        candidates = self.get_names()
                    else:
                        # Later words: match files/directories
                        candidates = self._get_path_completions(being_completed)

                    if candidates:
                        self.current_candidates = [c for c in candidates
                                                if c.startswith(text)]
                    else:
                        self.current_candidates = []
                except (NameError, AttributeError):
                    self.current_candidates = []

        try:
            return self.current_candidates[state]
        except IndexError:
            return None

    def _get_path_completions(self, path):
        """Get completion candidates for file/directory paths"""
        try:
            if not path:
                path = "."

            dir_path = os.path.dirname(path) or "."
            name_pattern = os.path.basename(path)

            entries = klayer_fs.list_directory(dir_path)
            return [entry['name'] for entry in entries 
                   if entry['name'].startswith(name_pattern)]
        except Exception:
            return []

    def _get_intro(self) -> str:
        """Generate enhanced intro message with system info"""
        try:
            resources = klayer_process.get_system_resources() if klayer_process.is_initialized() else {}
            cpu_percent = self.get_resource_value(resources, 'cpu', 'percent')
            mem_percent = self.get_resource_value(resources, 'memory', 'virtual', 'percent')
            disk_percent = self.get_resource_value(resources, 'disk', 'usage', 'percent')

            return f"""
╔══════════════════════════════════════════════════════════╗
║                 Welcome to Kaede OS (KOS)                ║
║                   Version: {self.kos_version}                     ║
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
            return f"Welcome to KOS {self.kos_version}. Type 'help' for commands.\n"

    def _get_prompt(self) -> str:
        """Generate enhanced shell prompt with git-like info"""
        cwd = klayer_fs.get_current_path().replace(self.kos_home, '~')
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

    def do_reboot(self, arg):
        """Reboot KOS - restart the operating system
        Usage: reboot"""
        print("Rebooting KOS...")
        self._cleanup()
        python = sys.executable
        os.execl(python, python, sys.argv[0])

    def do_shutdown(self, arg):
        """Shutdown KOS - exit the operating system
        Usage: shutdown"""
        print("Shutting down KOS...")
        self._cleanup()
        sys.exit(0)


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
                processes = klayer_process.get_process_tree() if klayer_process.is_initialized() else []
                self._display_process_tree(processes)
            else:
                processes = klayer_process.list_processes(refresh=True) if klayer_process.is_initialized() else []
                self._display_process_list(processes, full_format)

        except Exception as e:
            logger.error(f"Error in ps command: {e}")
            print(f"ps: {str(e)}")

    def _watch_processes(self, full_format: bool):
        """Watch process list in real-time"""
        try:
            if RICH_AVAILABLE and self.console:
                with Progress(
                    SpinnerColumn(),
                    *Progress.get_default_columns(),
                    TimeElapsedColumn(),
                    refresh_per_second=4
                ) as progress:
                    while True:
                        self.console.clear()
                        processes = klayer_process.list_processes(refresh=True) if klayer_process.is_initialized() else []
                        resources = klayer_process.get_system_resources() if klayer_process.is_initialized() else {}

                        self.console.print(Panel(
                            f"CPU: {self.get_resource_value(resources, 'cpu', 'percent'):.1f}% | "
                            f"MEM: {self.get_resource_value(resources, 'memory', 'virtual', 'percent'):.1f}% | "
                            f"Processes: {len(processes)}"
                        ))

                        self._display_process_list(processes, full_format)
                        time.sleep(2)
            else:
                while True:
                    processes = klayer_process.list_processes(refresh=True) if klayer_process.is_initialized() else []
                    print("Process list:")
                    for p in processes:
                        print(f"  PID: {p.pid}, Name: {p.name}")
                    time.sleep(2)
        except KeyboardInterrupt:
            return

    def _display_process_tree(self, tree: Dict[int, List[Any]], pid: int = 1, level: int = 0):
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
                self.console.print(
                    f"{prefix} {process.pid} ",
                    end=""
                )
                self.console.print(
                    f"[{status_color}]{process.name}[/{status_color}] "
                    f"({process.cpu_percent:.1f}% CPU, {process.memory_percent:.1f}% MEM)"
                )
            else:
                print(f"{prefix} {process.pid} {process.name} ({process.cpu_percent:.1f}% CPU, {process.memory_percent:.1f}% MEM)")
            self._display_process_tree(tree, process.pid, level + 1)

    def _display_process_list(self, processes: List[Any], full_format: bool):
        """Display process list with enhanced formatting"""
        if RICH_AVAILABLE and self.console:
            table = Table(title="Process List")

            if full_format:
                columns = [
                    "PID", "PPID", "USER", "PRI", "NI", "CPU%", "MEM%", 
                    "THR", "START", "TIME", "COMMAND"
                ]
            else:
                columns = ["PID", "TTY", "STAT", "TIME", "CMD"]

            for col in columns:
                table.add_column(col)

            sorted_processes = sorted(
                processes,
                key=lambda p: p.cpu_percent + p.memory_percent,
                reverse=True
            )

            for proc in sorted_processes[:20]:  # Show top 20 by default
                if full_format:
                    table.add_row(
                        str(proc.pid),
                        str(proc.ppid),
                        proc.username,
                        str(proc.priority),
                        str(proc.nice),
                        f"{proc.cpu_percent:.1f}",
                        f"{proc.memory_percent:.1f}",
                        str(proc.threads),
                        proc.create_time.strftime("%H:%M"),
                        self._format_proc_time(proc),
                        " ".join(proc.cmdline) if proc.cmdline else proc.name
                    )
                else:
                    table.add_row(
                        str(proc.pid),
                        "?",
                        proc.status[:1],
                        "00:00",
                        proc.name
                    )

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
                with Progress(
                    SpinnerColumn(),
                    *Progress.get_default_columns(),
                    TimeElapsedColumn(),
                    refresh_per_second=4
                ) as progress:
                    while True:
                        processes = klayer_process.list_processes(refresh=True) if klayer_process.is_initialized() else []
                        resources = klayer_process.get_system_resources() if klayer_process.is_initialized() else {}

                        self.console.clear()
                        self.console.print(f"KOS Top - {datetime.now().strftime('%H:%M:%S')}")
                        self.console.print(f"CPU: {self.get_resource_value(resources, 'cpu', 'percent'):.1f}% MEM: {self.get_resource_value(resources, 'memory', 'virtual', 'percent'):.1f}%")

                        table = Table(title="Process List")
                        columns = ["PID", "USER", "PR", "CPU%", "MEM%", "COMMAND"]
                        for col in columns:
                            table.add_column(col)

                        for proc in sorted(processes, key=lambda p: p.cpu_percent, reverse=True)[:20]:
                            table.add_row(
                                str(proc.pid),
                                proc.username,
                                str(proc.priority),
                                f"{proc.cpu_percent:.1f}",
                                f"{proc.memory_percent:.1f}",
                                proc.name
                            )

                        self.console.print(table)
                        time.sleep(2)
            else:
                while True:
                    processes = klayer_process.list_processes(refresh=True) if klayer_process.is_initialized() else []
                    print("Top processes:")
                    for p in sorted(processes, key=lambda p: p.cpu_percent, reverse=True)[:10]:
                        print(f"  PID: {p.pid}, Name: {p.name}, CPU%: {p.cpu_percent:.1f}")
                    time.sleep(2)
        except KeyboardInterrupt:
            return
        except Exception as e:
            logger.error(f"Error in top command: {e}")
            print(f"top: {str(e)}")

    def get_resource_value(self, resource_dict: Dict, *keys: str) -> float:
        """Safely get nested resource values with type checking"""
        try:
            value = resource_dict
            for key in keys:
                value = value[key]
            return float(value) if isinstance(value, (int, float)) else 0.0
        except (KeyError, TypeError, ValueError):
            return 0.0

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
                resources = klayer_process.get_system_resources() if klayer_process.is_initialized() else {}
                disk_info = resources.get('disk', {})
                usage = disk_info.get('usage', {})

                if not RICH_AVAILABLE or not self.console:
                    # Fallback to basic output if rich is not available
                    print("\nDisk Usage:")
                    print(f"Total Space: {usage.get('total', 0)/1024/1024:.2f} MB")
                    print(f"Used Space: {usage.get('used', 0)/1024/1024:.2f} MB")
                    print(f"Free Space: {usage.get('free', 0)/1024/1024:.2f} MB")
                    print(f"Usage: {usage.get('percent', 0):.1f}%")
                    return

                table = Table(title="Disk Usage")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="magenta")

                table.add_row("Total Space", f"{usage.get('total', 0)/1024/1024:.2f} MB")
                table.add_row("Used Space", f"{usage.get('used', 0)/1024/1024:.2f} MB")
                table.add_row("Free Space", f"{usage.get('free', 0)/1024/1024:.2f} MB")
                table.add_row("Usage", f"{usage.get('percent', 0):.1f}%")

                if io_info := disk_info.get('io'):
                    table.add_row("Read Operations", str(io_info.get('read_count', 0)))
                    table.add_row("Write Operations", str(io_info.get('write_count', 0)))

                self.console.print(table)

            elif command == 'check':
                if not klayer_fs.disk_manager:
                    print("Error: Disk manager not initialized")
                    return

                issues = klayer_fs.disk_manager.check_integrity()
                if not issues:
                    if RICH_AVAILABLE and self.console:
                        self.console.print("[green]✓ Filesystem integrity check passed[/green]")
                    else:
                        print("✓ Filesystem integrity check passed")
                else:
                    if RICH_AVAILABLE and self.console:
                        self.console.print("[red]! Filesystem integrity issues found:[/red]")
                    else:
                        print("! Filesystem integrity issues found:")
                    for issue in issues:
                        print(f"  - {issue}")

            elif command == 'repair':
                if not klayer_fs.disk_manager:
                    print("Error: Disk manager not initialized")
                    return

                if klayer_fs.disk_manager.repair_filesystem():
                    if RICH_AVAILABLE and self.console:
                        self.console.print("[green]✓ Filesystem repair completed successfully[/green]")
                    else:
                        print("✓ Filesystem repair completed successfully")
                else:
                    if RICH_AVAILABLE and self.console:
                        self.console.print("[red]✗ Failed to repair filesystem[/red]")
                    else:
                        print("✗ Failed to repair filesystem")

            else:
                print("Invalid disk command. Available commands: usage, check, repair")

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
                    table.add_row(
                        username,
                        status,
                        ", ".join(user_info["groups"]),
                        user_info["home"]
                    )

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

            entries = klayer_fs.list_directory(path, long_format=long_format)

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
                            oct(entry['permissions'])[2:],
                            entry['owner'],
                            entry['group'],
                            str(entry['size']),
                            entry['modified'].strftime("%Y-%m-%d %H:%M"),
                            entry['name']
                        )
                else:
                    table.add_column("Name")
                    for entry in entries:
                        table.add_row(entry if isinstance(entry, str) else entry['name'])

                self.console.print(table)
            else:
                if long_format:
                    for entry in entries:
                        print(f"{entry['type']} {oct(entry['permissions'])[2:]} {entry['owner']} {entry['group']} {entry['size']} {entry['modified']} {entry['name']}")
                else:
                    print("  ".join(entries if isinstance(entries[0], str) else [e['name'] for e in entries]))

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
                klayer_fs.change_directory(path)
                logger.debug(f"Changed directory to: {klayer_fs.get_current_path()}")
                self.prompt = self._get_prompt()  # Update prompt with new path
            except FileSystemError as e:
                print(f"cd: {str(e)}")

        except Exception as e:
            logger.error(f"Error in cd command: {e}")
            print(f"cd: {str(e)}")

    def do_pwd(self, arg):
        """Print working directory"""
        print(klayer_fs.get_current_path())

    def do_mkdir(self, arg):
        """Create directory with permissions"""
        try:
            args = shlex.split(arg)
            if not args:
                print("mkdir: missing operand")
                return

            path = args[0]
            mode = 0o755  # Default mode

            if "-m" in args:
                mode_idx = args.index("-m") + 1
                if mode_idx < len(args):
                    mode = int(args[mode_idx], 8)

            klayer_fs.create_directory(path, mode)
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

    def do_uname(self, arg):
        """Display system information
        Usage: uname [-a]
        -a: show all information"""
        try:
            show_all = '-a' in arg
            info = {
                'system': 'KOS',
                'release': self.kos_version,
                'machine': 'Python Virtual System',
                'processor': 'Virtual CPU',
                'platform': sys.platform
            }

            if show_all:
                if RICH_AVAILABLE and self.console:
                    table = Table(title="System Information")
                    table.add_column("Component")
                    table.add_column("Value")
                    for k, v in info.items():
                        table.add_row(k.capitalize(), str(v))
                    self.console.print(table)
                else:
                    for k, v in info.items():
                        print(f"{k.capitalize()}: {v}")
            else:
                print(info['system'])
        except Exception as e:
            print(f"uname: {str(e)}")

    def do_timedatectl(self, arg):
        """Display system time and date information"""
        try:
            now = datetime.now()
            if RICH_AVAILABLE and self.console:
                table = Table(title="System Time Information")
                table.add_column("Setting")
                table.add_column("Value")
                table.add_row("Local time", now.strftime("%Y-%m-%d %H:%M:%S"))
                table.add_row("Universal time", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
                table.add_row("Timezone", time.tzname[0])
                self.console.print(table)
            else:
                print(f"Local time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"Universal time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"Timezone: {time.tzname[0]}")
        except Exception as e:
            print(f"timedatectl: {str(e)}")

    def do_lscpu(self, arg):
        """Display CPU architecture information"""
        try:
            cpu_info = psutil.cpu_freq()
            cpu_count = psutil.cpu_count()
            if RICH_AVAILABLE and self.console:
                table = Table(title="CPU Information")
                table.add_column("Property")
                table.add_column("Value")
                table.add_row("Architecture", platform.machine())
                table.add_row("CPU(s)", str(cpu_count))
                if cpu_info:
                    table.add_row("CPU MHz", f"{cpu_info.current:.2f}")
                self.console.print(table)
            else:
                print(f"Architecture: {platform.machine()}")
                print(f"CPU(s): {cpu_count}")
                if cpu_info:
                    print(f"CPU MHz: {cpu_info.current:.2f}")
        except Exception as e:
            print(f"lscpu: {str(e)}")

    def do_crontab(self, arg):
        """Manage cron jobs
        Usage: crontab [-l|-e]
        -l: list cron jobs
        -e: edit cron jobs"""
        try:
            args = shlex.split(arg)
            if '-l' in args:
                # Simulated cron jobs listing
                if RICH_AVAILABLE and self.console:
                    table = Table(title="Current Cron Jobs")
                    table.add_column("Schedule")
                    table.add_column("Command")
                    table.add_row("0 * * * *", "hourly_backup.sh")
                    table.add_row("0 0 * * *", "daily_cleanup.sh")
                    self.console.print(table)
                else:
                    print("0 * * * * hourly_backup.sh")
                    print("0 0 * * * daily_cleanup.sh")
            elif '-e' in args:
                print("Opening crontab editor...")
                # In a real implementation, this would open an editor
                print("Simulated crontab editor - feature not implemented")
            else:
                print("Usage: crontab [-l|-e]")
        except Exception as e:
            print(f"crontab: {str(e)}")

    def do_bg(self, arg):
        """Run command in background
        Usage: command &"""
        try:
            if not arg:
                print("bg: missing command")
                return
            print(f"Running '{arg}' in background")
            # Simulate background process
            job_id = len(self.background_jobs) + 1
            self.background_jobs[job_id] = {"cmd": arg, "status": "running"}
            print(f"[{job_id}] Running")
        except Exception as e:
            print(f"bg: {str(e)}")

    def do_fg(self, arg):
        """Bring background job to foreground
        Usage: fg %job_number"""
        try:
            if not arg or not arg.startswith('%'):
                print("fg: usage: fg %job_number")
                return
            job_id = int(arg[1:])
            if job_id in self.background_jobs:
                print(f"Bringing job {job_id} ({self.background_jobs[job_id]['cmd']}) to foreground")
                # Simulate bringing process to foreground
                del self.background_jobs[job_id]
            else:
                print(f"fg: job {job_id} not found")
        except Exception as e:
            print(f"fg: {str(e)}")

    def do_jobs(self, arg):
        """List background jobs"""
        try:
            if not self.background_jobs:
                print("No background jobs")
                return
            if RICH_AVAILABLE and self.console:
                table = Table(title="Background Jobs")
                table.add_column("Job ID")
                table.add_column("Status")
                table.add_column("Command")
                for job_id, info in self.background_jobs.items():
                    table.add_row(str(job_id), info['status'], info['cmd'])
                self.console.print(table)
            else:
                for job_id, info in self.background_jobs.items():
                    print(f"[{job_id}] {info['status']} {info['cmd']}")
        except Exception as e:
            print(f"jobs: {str(e)}")

    def do_df(self, arg):
        """Report file system disk space usage
        Usage: df [-h]
        -h: print sizes in human readable format"""
        try:
            human_readable = '-h' in arg
            usage = psutil.disk_usage('/')

            if human_readable:
                total = f"{usage.total / (1024**3):.1f}G"
                used = f"{usage.used / (1024**3):.1f}G"
                free = f"{usage.free / (1024**3):.1f}G"
            else:
                total = str(usage.total)
                used = str(usage.used)
                free = str(usage.free)

            if RICH_AVAILABLE and self.console:
                table = Table(title="Disk Usage")
                table.add_column("Filesystem")
                table.add_column("Size")
                table.add_column("Used")
                table.add_column("Avail")
                table.add_column("Use%")
                table.add_row("/", total, used, free, f"{usage.percent}%")
                self.console.print(table)
            else:
                print(f"Filesystem     Size    Used    Avail   Use%")
                print(f"/    {total:>8} {used:>8} {free:>8} {usage.percent:>3}%")
        except Exception as e:
            print(f"df: {str(e)}")

    def do_top(self, arg):
        """Display system tasks"""
        try:
            while True:
                os.system('clear')
                cpu_percent = psutil.cpu_percent()
                mem = psutil.virtual_memory()
                processes = sorted(
                    psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']),
                    key=lambda p: p.info['cpu_percent'],
                    reverse=True
                )[:10]

                if RICH_AVAILABLE and self.console:
                    self.console.print(f"CPU Usage: {cpu_percent}%")
                    self.console.print(f"Memory Usage: {mem.percent}%")
                    table = Table()
                    table.add_column("PID")
                    table.add_column("Name")
                    table.add_column("CPU%")
                    table.add_column("MEM%")
                    for p in processes:
                        table.add_row(
                            str(p.info['pid']),
                            p.info['name'],
                            f"{p.info['cpu_percent']:.1f}",
                            f"{p.info['memory_percent']:.1f}"
                        )
                    self.console.print(table)
                else:
                    print(f"CPU Usage: {cpu_percent}%")
                    print(f"Memory Usage: {mem.percent}%")
                    print("\nPID\tNAME\t\tCPU%\tMEM%")
                    for p in processes:
                        print(f"{p.info['pid']}\t{p.info['name'][:15]}\t{p.info['cpu_percent']:.1f}\t{p.info['memory_percent']:.1f}")

                time.sleep(2)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f"top: {str(e)}")

    def do_kill(self, arg):
        """Terminate a process
        Usage: kill [-9] pid"""
        try:
            args = shlex.split(arg)
            force = '-9' in args
            args = [a for a in args if not a.startswith('-')]

            if not args:
                print("kill: usage: kill [-9] pid")
                return

            pid = int(args[0])
            try:
                process = psutil.Process(pid)
                if force:
                    process.kill()
                else:
                    process.terminate()
                print(f"Process {pid} terminated")
            except psutil.NoSuchProcess:
                print(f"kill: ({pid}) - No such process")
        except Exception as e:
            print(f"kill: {str(e)}")

    def do_jobs(self, arg):
        """Display status of jobs"""
        try:
            running_jobs = [p for p in psutil.process_iter(['pid', 'name', 'status'])
                          if p.info['status'] == 'running']

            if RICH_AVAILABLE and self.console:
                table = Table(title="Running Jobs")
                table.add_column("JOB")
                table.add_column("PID")
                table.add_column("Command")
                for i, job in enumerate(running_jobs, 1):
                    table.add_row(f"[{i}]", str(job.info['pid']), job.info['name'])
                self.console.print(table)
            else:
                for i, job in enumerate(running_jobs, 1):
                    print(f"[{i}] {job.info['pid']} {job.info['name']}")
        except Exception as e:
            print(f"jobs: {str(e)}")

    def do_fg(self, arg):
        """Bring job to foreground
        Usage: fg %job_number"""
        try:
            if not arg.startswith('%'):
                print("fg: usage: fg %job_number")
                return

            job_num = int(arg[1:])
            # This is a simplified implementation since we don't have real job control
            print(f"Brought job {job_num} to foreground")
        except Exception as e:
            print(f"fg: {str(e)}")

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
            content = klayer_fs.read_file(path)

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

            recursive = "-r" in args or "-R" in args
            force = "-f" in args

            # Filter out options
            paths = [a for a in args if not a.startswith("-")]

            for path in paths:
                try:
                    klayer_fs.remove(path, recursive=recursive)
                    logger.info(f"Removed: {path}")
                except FileSystemError as e:
                    if not force:
                        print(f"rm: cannot remove '{path}': {str(e)}")
                        return
                    logger.warning(f"Forced removal despite error: {path}")

        except Exception as e:
            logger.error(f"Error in rm command: {e}")
            print(f"rm: {str(e)}")

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

            klayer_fs.copy(source, dest, recursive=recursive)
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

            klayer_fs.move(source, dest)
            logger.info(f"Moved {source to {dest}")

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
            klayer_fs.chmod(path, mode_int)
            logger.info(f"Changed mode of {path} to {mode}")

        except Exception as e:
            logger.error(f"Error in chmod command: {e}")
            print(f"chmod: {str(e)}")

    def do_head(self, arg):
        """Output first part of files"""
        try:
            args = shlex.split(arg)
            if not args:
                print("head: missing file operand")
                return

            lines = 10  # Default number of lines
            if "-n" in args:
                n_idx = args.index("-n")
                if n_idx + 1 < len(args):
                    try:
                        lines = int(args[n_idx + 1])
                        args.pop(n_idx + 1)
                        args.pop(n_idx)
                    except ValueError:
                        print("head: invalid number of lines")
                        return

            for path in args:
                try:
                    content = klayer_fs.read_file(path)
                    if RICH_AVAILABLE and self.console:
                        self.console.print(f"==> {path} <==")
                        for line in content.split('\n')[:lines]:
                            self.console.print(line)
                    else:
                        print(f"==> {path} <==")
                        print('\n'.join(content.split('\n')[:lines]))
                except Exception as e:
                    print(f"head: {path}: {str(e)}")

        except Exception as e:
            logger.error(f"Error in head command: {e}")
            print(f"head: {str(e)}")

    def do_tail(self, arg):
        """Output last part of files"""
        try:
            args = shlex.split(arg)
            if not args:
                print("tail: missing file operand")
                return

            lines = 10  # Default number of lines
            follow = False
            if "-n" in args:
                n_idx = args.index("-n")
                if n_idx + 1 < len(args):
                    try:
                        lines = int(args[n_idx + 1])
                        args.pop(n_idx + 1)
                        args.pop(n_idx)
                    except ValueError:
                        print("tail: invalid number of lines")
                        return
            if "-f" in args:
                follow = True
                args.remove("-f")

            for path in args:
                try:
                    if follow:
                        self._tail_follow(path)
                    else:
                        content = klayer_fs.read_file(path)
                        if RICH_AVAILABLE and self.console:
                            self.console.print(f"==> {path} <==")
                            for line in content.split('\n')[-lines:]:
                                self.console.print(line)
                        else:
                            print(f"==> {path} <==")
                            print('\n'.join(content.split('\n')[-lines:]))
                except Exception as e:
                    print(f"tail: {path}: {str(e)}")

        except Exception as e:
            logger.error(f"Error in tail command: {e}")
            print(f"tail: {str(e)}")

    def _tail_follow(self, path):
        """Follow file content in real-time"""
        try:
            prev_content = ""
            while True:
                try:
                    content = klayer_fs.read_file(path)
                    if content != prev_content:
                        new_lines = content[len(prev_content):]
                        if RICH_AVAILABLE and self.console:
                            self.console.print(new_lines, end='')
                        else:
                            print(new_lines, end='')
                        prev_content = content
                    time.sleep(1)
                except KeyboardInterrupt:
                    return
        except Exception as e:
            print(f"tail: error following {path}: {str(e)}")

    def do_wc(self, arg):
        """Print newline, word, and byte counts for files"""
        try:
            args = shlex.split(arg)
            if not args:
                print("wc: missing file operand")
                return

            total_lines = total_words = total_bytes = 0
            show_lines = show_words = show_bytes = True

            # Parse options
            if "-l" in args:
                show_words = show_bytes = False
                args.remove("-l")
            elif "-w" in args:
                show_lines = show_bytes = False
                args.remove("-w")
            elif "-c" in args:
                show_lines = show_words = False
                args.remove("-c")

            for path in args:
                try:
                    content = klayer_fs.read_file(path)
                    lines = content.count('\n') + (not content.endswith('\n'))
                    words = len(content.split())
                    bytes_count = len(content.encode('utf-8'))

                    total_lines += lines
                    total_words += words
                    total_bytes += bytes_count

                    counts = []
                    if show_lines:
                        counts.append(str(lines))
                    if show_words:
                        counts.append(str(words))
                    if show_bytes:
                        counts.append(str(bytes_count))

                    if RICH_AVAILABLE and self.console:
                        self.console.print(f"{' '.join(counts)} {path}")
                    else:
                        print(f"{' '.join(counts)} {path}")

                except Exception as e:
                    print(f"wc: {path}: {str(e)}")

            # Print totals if more than one file
            if len(args) > 1:
                totals = []
                if show_lines:
                    totals.append(str(total_lines))
                if show_words:
                    totals.append(str(total_words))
                if show_bytes:
                    totals.append(str(total_bytes))

                if RICH_AVAILABLE and self.console:
                    self.console.print(f"{' '.join(totals)} total")
                else:
                    print(f"{' '.join(totals)} total")

        except Exception as e:
            logger.error(f"Error in wc command: {e}")
            print(f"wc: {str(e)}")

    def do_sort(self, arg):
        """Sort lines of text files"""
        try:
            args = shlex.split(arg)
            if not args:
                print("sort: missing file operand")
                return

            reverse = "-r" in args
            if reverse:
                args.remove("-r")

            numeric = "-n" in args
            if numeric:
                args.remove("-n")

            ignore_case = "-f" in args
            if ignore_case:
                args.remove("-f")

            for path in args:
                try:
                    content = klayer_fs.read_file(path)
                    lines = content.split('\n')

                    # Sort lines based on options
                    if numeric:
                        lines.sort(key=lambda x: float(x.strip() or 0), reverse=reverse)
                    elif ignore_case:
                        lines.sort(key=str.casefold, reverse=reverse)
                    else:
                        lines.sort(reverse=reverse)

                    if RICH_AVAILABLE and self.console:
                        for line in lines:
                            self.console.print(line)
                    else:
                        print('\n'.join(lines))

                except Exception as e:
                    print(f"sort: {path}: {str(e)}")

        except Exception as e:
            logger.error(f"Error in sort command: {e}")
            print(f"sort: {str(e)}")

    def do_uniq(self, arg):
        """Report or omit repeated lines"""
        try:
            args = shlex.split(arg)
            if not args:
                print("uniq: missing file operand")
                return

            count = "-c" in args
            if count:
                args.remove("-c")

            repeated = "-d" in args
            if repeated:
                args.remove("-d")

            unique = "-u" in args
            if unique:
                args.remove("-u")

            ignore_case = "-i" in args
            if ignore_case:
                args.remove("-i")

            for path in args:
                try:
                    content = klayer_fs.read_file(path)
                    lines = content.split('\n')

                    # Process lines based on options
                    current_line = None
                    current_count = 0

                    for line in lines:
                        compare_line = line.lower() if ignore_case else line

                        if current_line is None:
                            current_line = compare_line
                            current_count = 1
                            continue

                        if compare_line == current_line:
                            current_count += 1
                        else:
                            if count:
                                if RICH_AVAILABLE and self.console:
                                    self.console.print(f"{current_count:7d} {line}")
                                else:
                                    print(f"{current_count:7d} {line}")
                            elif repeated and current_count > 1:
                                if RICH_AVAILABLE and self.console:
                                    self.console.print(line)
                                else:
                                    print(line)
                            elif unique and current_count == 1:
                                if RICH_AVAILABLE and self.console:
                                    self.console.print(line)
                                else:
                                    print(line)
                            elif not (repeated or unique):
                                if RICH_AVAILABLE and self.console:
                                    self.console.print(line)
                                else:
                                    print(line)

                            current_line = compare_line
                            current_count = 1

                except Exception as e:
                    print(f"uniq: {path}: {str(e)}")

        except Exception as e:
            logger.error(f"Error in uniq command: {e}")
            print(f"uniq: {str(e)}")

    def do_cal(self, arg):
        """Display a calendar"""
        try:
            args = shlex.split(arg)

            # Import the calendar module
            import calendar
            from datetime import datetime

            # Get current date
            now = datetime.now()

            # Parse arguments
            year = now.year
            month = now.month

            if len(args) >= 2:
                try:
                    month = int(args[0])
                    year = int(args[1])
                except ValueError:
                    print("cal: invalid month or year")
                    return
            elif len(args) == 1:
                try:
                    month = int(args[0])
                except ValueError:
                    print("cal: invalid month")
                    return

            # Validate month and year
            if not (1 <= month <= 12):
                print("cal: month must be between 1 and 12")
                return

            if not (1 <= year <= 9999):
                print("cal: year must be between 1 and 9999")
                return

            # Create calendar
            cal = calendar.TextCalendar()
            cal_str = cal.formatmonth(year, month)

            if RICH_AVAILABLE and self.console:
                # Create a panel with the calendar
                panel = Panel(
                    cal_str,
                    title=f"{calendar.month_name[month]} {year}",
                    border_style="blue"
                )
                self.console.print(panel)
            else:
                print(cal_str)

        except Exception as e:
            logger.error(f"Error in cal command: {e}")
            print(f"cal: {str(e)}")

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
                    content = klayer_fs.read_file(path)
                    lines = content.split('\n')
                    for i, line in enumerate(lines, 1):
                        if (ignore_case and pattern.lower() in line.lower()) or pattern in line:
                            if RICH_AVAILABLE and self.console:
                                highlighted = line.replace(pattern, f"[red]{pattern}[/red]")
                                self.console.print(f"{path}:{i}: {highlighted}")
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

            results = klayer_fs.find(
                path, 
                pattern=pattern,
                file_type=type_filter,
                name=name_filter
            )

            if RICH_AVAILABLE and self.console:
                table = Table(title="Find Results")
                table.add_column("Path")
                table.add_column("Type")
                table.add_column("Size")

                for result in results:
                    table.add_row(
                        result['path'],
                        result['type'],
                        str(result['size'])
                    )
                self.console.print(table)
            else:
                for result in results:
                    print(f"{result['path']} ({result['type']}, {result['size']} bytes)")

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
                klayer_fs.touch(path)
                logger.info(f"Updated timestamp: {path}")

        except Exception as e:
            logger.error(f"Error in touch command: {e}")
            print(f"touch: {str(e)}")

    def do_tree(self, arg):
        """Display directory structure"""
        try:
            path = arg.strip() or "."
            tree_data = klayer_fs.get_directory_tree(path)

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

            if username != self.us.current_user and not self.us.can_kudo(self.us.current_user):
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
                print(f"Groups for {username}: {', '.join(user_info['groups'])}")

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

    def do_uname(self, arg):
        """Print system information"""
        try:
            if RICH_AVAILABLE and self.console:
                table = Table(title="System Information")
                table.add_column("Component")
                table.add_column("Value")

                table.add_row("Operating System", "KOS")
                table.add_row("Version", self.kos_version)
                table.add_row("Machine", "Python Virtual System")
                table.add_row("Processor", "Virtual CPU")
                table.add_row("Platform", sys.platform)

                self.console.print(table)
            else:
                print(f"KOS version {self.kos_version} on {sys.platform}")

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
                self.console.print(f"Uptime: {days} days, {hours} hours, {minutes} minutes")
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
            resources = klayer_process.get_system_resources() if klayer_process.is_initialized() else {}
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

                table.add_row(
                    "Memory",
                    format_bytes(memory['total']),
                    format_bytes(memory['used']),
                    format_bytes(memory['free']),
                    format_bytes(memory['available'])
                )
                table.add_row(
                    "Swap",
                    format_bytes(swap['total']),format_bytes(swap['used']),
                    format_bytes(swap['free']),
                    "-"
                )
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

    def do_sysinfo(self, arg):
        """Show system statistics"""
        try:
            resources = klayer_process.get_system_resources() if klayer_process.is_initialized() else {}
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
                    cpu_info.append(f"Frequency: {resources['cpu']['freq']['current']}MHz")
                table.add_row("CPU", "\n".join(cpu_info))

                # Memory Information
                mem = resources['memory']['virtual']
                table.add_row(
                    "Memory",
                    f"Total: {mem['total']/1024/1024:.1f}MB\n"
                    f"Used: {mem['used']/1024/1024:.1f}MB ({mem['percent']}%)\n"
                    f"Available: {mem['available']/1024/1024:.1f}MB"
                )

                # Disk Information
                disk = resources['disk']['usage']
                table.add_row(
                    "Disk",
                    f"Total: {disk['total']/1024/1024:.1f}MB\n"
                    f"Used: {disk['used']/1024/1024:.1f}MB ({disk['percent']}%)\n"
                    f"Free: {disk['free']/1024/1024:.1f}MB"
                )

                # Network Information
                if resources['network']['io']:
                    net = resources['network']['io']
                    table.add_row(
                        "Network",
                        f"Sent: {net['bytes_sent']/1024:.1f}KB\n"
                        f"Received: {net['bytes_recv']/1024:.1f}KB\n"
                        f"Connections: {resources['network']['connections']}"
                    )

                self.console.print(table)
            else:
                print("\nSystem Statistics:")
                print(f"CPU Usage: {resources['cpu']['percent']}%")
                print(f"Memory Used: {resources['memory']['virtual']['percent']}%")
                print(f"Disk Used: {resources['disk']['usage']['percent']}%")
                if resources['network']['io']:
                    print(f"Network Connections: {resources['network']['connections']}")

        except Exception as e:
            logger.error(f"Error in sysinfo command: {e}")
            print(f"sysinfo: {str(e)}")

    def postcmd(self, stop, line):
        """Save command history after execution"""
        self._save_history()
        return stop

    def get_similar_commands(self, cmd: str) -> List[str]:
        """Find similar commands using fuzzy matching"""
        import difflib

        threshold = 0.6  # Similarity threshold
        commands = self.get_names()  # Get all available commands
        matches = []

        # Use get_close_matches for fuzzy matching
        similar = get_close_matches(cmd, commands, n=3, cutoff=threshold)
        if similar:
            matches.extend(similar)

        return matches

    def default(self, line: str):
        """Handle unknown commands by checking if they're installed apps"""
        try:
            # Split command and arguments
            parts = shlex.split(line)
            if not parts:
                return False

            cmd = parts[0]
            args = parts[1:] if len(parts) > 1 else []

            # First check kos_apps directory
            app_path = os.path.join('kos_apps', cmd, f'{cmd}.py')
            if os.path.exists(app_path) and os.access(app_path, os.X_OK):
                subprocess.run(['python3', app_path] + args)
                return True

            # Check if it's an installed app
            if self.km.run_program(cmd, args):
                return True

            # Not an app, show error
            print(f"kos: command not found: {cmd}")
            return False
        except Exception as e:
            logger.error(f"Error in default command: {e}")
            print(f"kos: {str(e)}")
            return False

    def do_intro(self, arg):
        """Display system information"""
        print(self.intro)

    def do_help(self, arg):
        """Show help for commands"""
        try:
            if not arg:
                # Show general help message
                if RICH_AVAILABLE and self.console:
                    table = Table(title="KOS Command Reference")
                    for category, commands in self.command_categories.items():
                        table.add_row(category, ", ".join(commands))
                    self.console.print(table)
                else:
                    print("KOS Command Reference\n")
                    for category, commands in self.command_categories.items():
                        print(f"{category}: {', '.join(commands)}")
            else:
                # Show detailed help for a specific command
                if arg in self.get_names():
                    doc = getattr(self, f"do_{arg}").__doc__
                    if RICH_AVAILABLE and self.console:
                        panel = Panel(doc, title=f"Help: {arg}")
                        self.console.print(panel)
                    else:
                        print(f"Help: {arg}\n{doc}")
                else:
                    similar_commands = self.get_similar_commands(arg)
                    if similar_commands:
                        print(f"No help for command '{arg}'. Did you mean:\n{', '.join(similar_commands)}?")
                    else:
                        print(f"No help found for command '{arg}'.")

        except Exception as e:
            logger.error(f"Error in help command: {e}")
            print(f"help: {str(e)}")


    def emptyline(self):
        """Do nothing on empty line"""
        pass

    def do_chown(self, arg):
        """Change file owner"""
        try:
            args = shlex.split(arg)
            if len(args) != 2:
                print("chown: usage: chown <owner> <file>")
                return
            owner = args[0]
            path = args[1]
            klayer_fs.chown(path, owner)
            print(f"Changed owner of {path} to {owner}")
        except Exception as e:
            print(f"chown: {str(e)}")

    def do_id(self, arg):
        """Show user and group IDs"""
        try:
            username = arg.strip() or self.us.current_user
            user_info = self.us.get_user_info(username)
            if RICH_AVAILABLE and self.console:
                table = Table(title=f"User and Group IDs for {username}")
                table.add_column("ID Type")
                table.add_column("ID")
                table.add_row("UID", str(user_info["uid"]))
                table.add_row("GID", str(user_info["gid"]))
                self.console.print(table)
            else:
                print(f"UID={user_info['uid']}, GID={user_info['gid']}")
        except Exception as e:
            print(f"id: {str(e)}")

    def do_cmp(self, arg):
        """Compare two files"""
        try:
            args = shlex.split(arg)
            if len(args) != 2:
                print("cmp: usage: cmp <file1> <file2>")
                return
            file1 = args[0]
            file2 = args[1]
            if klayer_fs.compare_files(file1, file2):
                print(f"Files {file1} and {file2} are identical")
            else:
                print(f"Files {file1} and {file2} are different")
        except Exception as e:
            print(f"cmp: {str(e)}")

    def do_diff(self, arg):
        """Compare two files line by line"""
        try:
            args = shlex.split(arg)
            if len(args) != 2:
                print("diff: usage: diff <file1> <file2>")
                return
            file1 = args[0]
            file2 = args[1]
            diff_result = klayer_fs.diff_files(file1, file2)
            if diff_result:
                if RICH_AVAILABLE and self.console:
                    self.console.print(diff_result)
                else:
                    print(diff_result)
            else:
                print(f"Files {file1} and {file2} are identical")
        except Exception as e:
            print(f"diff: {str(e)}")

    def do_sed(self, arg):
        """Stream editor for text transformations"""
        try:
            args = shlex.split(arg)
            if len(args) < 2:
                print("sed: usage: sed <command> <file>")
                return
            command = args[0]
            path = args[1]

            content = klayer_fs.read_file(path)
            processed_content = klayer_fs.process_sed(content, command)
            if RICH_AVAILABLE and self.console:
                self.console.print(processed_content)
            else:
                print(processed_content)
        except Exception as e:
            print(f"sed: {str(e)}")


    def do_awk(self, arg):
        """Text processing utility"""
        try:
            args = shlex.split(arg)
            if len(args) < 2:
                print("awk: usage: awk '<script>' <file>")
                return
            script = args[0]
            path = args[1]
            content = klayer_fs.read_file(path)
            processed_content = klayer_fs.process_awk(content, script)
            if RICH_AVAILABLE and self.console:
                self.console.print(processed_content)
            else:
                print(processed_content)
        except Exception as e:
            print(f"awk: {str(e)}")
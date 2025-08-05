"""KOS Shell Commands"""
import cmd
import shlex
import getpass
import logging
from typing import Optional, Dict, List

# Configure logger
logger = logging.getLogger(__name__)

# Import the actual shell from the shell module
try:
    from .shell.shell import KOSShell as KaedeShell
    _SHELL_IMPORTED = True
except ImportError:
    # Will define fallback shell below
    _SHELL_IMPORTED = False
    logger.warning("Could not import KOSShell from shell module, using basic shell")

# Basic imports for fallback shell
try:
    from rich.console import Console
    from rich.table import Table
except ImportError:
    print("Warning: Rich library not available, falling back to basic output")
    Console = None
    Table = None
import re
import time
from datetime import datetime
from .package_manager import KpmManager
from .docs import ManualSystem 
from .filesystem import FileSystem
from .user_system import UserSystem
from .filesystem import FileNotFound, NotADirectory, FileSystemError

# Import Kaede integration
try:
    from .kaede.shell_integration import KaedeShellCommands
    KAEDE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Kaede language not available: {e}")
    KAEDE_AVAILABLE = False

class CommandContext:
    """Context for command execution"""
    def __init__(self, original_user: str, is_sudo: bool = False):
        self.original_user = original_user
        self.is_sudo = is_sudo

# Only define KaedeShell if we couldn't import it
if not _SHELL_IMPORTED:
    class KaedeShell(cmd.Cmd):
        intro = 'Welcome to Kaede OS (KOS) 1.0.0\nType help or ? to list commands.\n'
        prompt = 'kos$ '

    def __init__(self, filesystem: FileSystem, kpm_manager: KpmManager, user_system: UserSystem):
        super().__init__()
        self.fs = filesystem
        self.km = kpm_manager 
        self.us = user_system
        self.console = Console() if Console else None
        self.prompt = self.us.get_prompt()

        # Initialize Kaede integration
        self.kaede_commands = None
        if KAEDE_AVAILABLE:
            try:
                self.kaede_commands = KaedeShellCommands(self)
                print("✓ Kaede programming language loaded")
            except Exception as e:
                print(f"✗ Failed to load Kaede language: {e}")
                logger.error(f"Kaede initialization failed: {e}", exc_info=True)

        self.env_vars = {
            "PATH": "/bin:/usr/bin",
            "HOME": self.us.get_user_info().get("home", "/home/user"),
            "USER": self.us.current_user,
            "SHELL": "/bin/ksh",
            "LANG": "en_US.UTF-8",
            "TERM": "xterm-256color"
        }

        # Simple command categories for help system
        self.command_categories = {
            "File Operations": ["ls", "cd", "pwd", "mkdir", "touch", "cat", "rm", "cp", "mv"],
            "System Operations": ["whoami", "hostname", "su", "useradd", "userdel", "kudo"],
            "Package Management": ["kpm"],
            "Network Tools": ["ping", "netstat", "wget", "curl"],
            "Programming": ["kaede", "kaedeinfo", "kaedeproject"] if KAEDE_AVAILABLE else []
        }

        # Initialize manual system
        self.man_system = ManualSystem()

        # Command history optimization
        self.cmd_history = []
        self.history_limit = 1000

        # Command aliases
        self.aliases = {
            'll': 'ls -l',
            'la': 'ls -a',
            'l': 'ls -CF',
            'kd': 'kaede',  # Short alias for Kaede
            'kinfo': 'kaedeinfo',
            'kproj': 'kaedeproject'
        }
        
    def emptyline(self):
        """Do nothing on empty line"""
        return False

    def cmdloop(self, intro=None):
        """Override cmdloop to handle keyboard interrupts"""
        if intro is not None:
            self.intro = intro
        if self.intro:
            print(self.intro)
        stop = None
        while not stop:
            try:
                if self.cmdqueue:
                    line = self.cmdqueue.pop(0)
                else:
                    line = input(self.prompt)
                line = self.precmd(line)
                stop = self.onecmd(line)
                stop = self.postcmd(stop, line)
            except KeyboardInterrupt:
                print("^C")
                continue
            except EOFError:
                print()
                return True
            except Exception as e:
                print(f"Error: {str(e)}")
                continue

    def precmd(self, line: str) -> str:
        """Pre-process command before execution"""
        if line:
            # Update environment variables
            self.env_vars["USER"] = self.us.current_user
            self.env_vars["HOME"] = self.us.get_user_info().get("home", "/home/user")
            self.prompt = self.us.get_prompt()
            
            # Handle aliases
            if line in self.aliases:
                line = self.aliases[line]
        return line

    def postcmd(self, stop: bool, line: str) -> bool:
        """Post-process command after execution"""
        if not stop and line:
            # Add to command history
            if len(self.cmd_history) >= self.history_limit:
                self.cmd_history.pop(0)
            self.cmd_history.append(line)
            # Update prompt after each command
            self.prompt = self.us.get_prompt()
        return stop

    def default(self, line: str) -> bool:
        """Handle unknown commands by checking if they are applications."""
        # Skip empty lines
        if not line or not line.strip():
            return False
            
        # Parse command and arguments
        try:
            cmd_parts = shlex.split(line)
        except ValueError as e:
            print(f"kos: error parsing command: {str(e)}")
            return False
            
        if not cmd_parts:
            return False
            
        cmd_name = cmd_parts[0]
        args = cmd_parts[1:] if len(cmd_parts) > 1 else []
        
        try:
            # First try built-in commands
            if hasattr(self, f'do_{cmd_name}'):
                return getattr(self, f'do_{cmd_name}')(' '.join(args))
                
            # Then try to run as an application through package manager
            if hasattr(self.km, 'run_program'):
                try:
                    if self.km.run_program(cmd_name, args):
                        return False
                except Exception as e:
                    print(f"kos: error running {cmd_name}: {str(e)}")
                    logger.error(f"Error running {cmd_name}: {str(e)}", exc_info=True)
                    return False
            
            # Check app index
            if hasattr(self.km, 'app_index'):
                app = self.km.app_index.get_app(cmd_name)
                if not app:
                    app = self.km.app_index.get_app_by_alias(cmd_name)
                
                if app:
                    logger.info(f"Running app from index: {cmd_name}")
                    try:
                        if self.km.run_program(cmd_name, args):
                            return False
                    except Exception as e:
                        print(f"kos: error running {cmd_name}: {str(e)}")
                        logger.error(f"Error running {cmd_name}: {str(e)}", exc_info=True)
                        return False
            
            # Check package database
            if hasattr(self.km, 'package_db'):
                try:
                    installed_packages = self.km.package_db.list_installed()
                    for pkg in installed_packages:
                        if pkg.name == cmd_name:
                            logger.info(f"Running installed package: {cmd_name}")
                            if self.km.run_program(cmd_name, args):
                                return False
                except Exception as e:
                    logger.error(f"Error accessing package database: {str(e)}", exc_info=True)
            
            # Command not found
            print(f"kos: command not found: {cmd_name}")
            return False
            
        except SystemExit as e:
            # Catch any SystemExit exceptions from applications
            print(f"kos: application exited with code {getattr(e, 'code', 1)}")
            return False
            
        except KeyboardInterrupt:
            # Handle Ctrl+C
            print("^C")
            return False
            
        except Exception as e:
            # Catch-all for any other exceptions
            print(f"kos: error executing command: {str(e)}")
            logger.error(f"Command execution error: {str(e)}", exc_info=True)
            return False

    def do_help(self, arg):
        """Show help about commands"""
        if arg:
            try:
                doc = getattr(self, f'do_{arg}').__doc__
                if doc:
                    print(doc)
                else:
                    print(f"No help found for '{arg}'")
            except AttributeError:
                print(f"No such command: '{arg}'")
            return

        print("\nAvailable Commands:")
        for category, commands in self.command_categories.items():
            print(f"\n{category}:")
            for cmd in commands:
                # Get just the first line of the docstring
                doc = getattr(self, f'do_{cmd}').__doc__ or ""
                brief = doc.split('\n')[0]  
                print(f"  {cmd:<12} {brief}")
        
        print("\nType 'help <command>' for detailed help on a specific command")

    def _execute_with_context(self, cmd: str, args: str, context: Optional[CommandContext] = None) -> None:
        """Execute a command with given context"""
        try:
            # If this is a sudo operation, temporarily switch to root
            original_user = None
            original_is_root = False
            if context and context.is_sudo:
                logger.debug(f"Sudo operation - Original user: {self.us.current_user}")
                original_user = self.us.current_user
                original_is_root = self.us.current_user_is_root()
                self.us.current_user = self.us.ROOT_USERNAME
                self.us.users[self.us.current_user]["is_root"] = True
                logger.debug(f"Elevated to root: {self.us.current_user}, is_root: {self.us.current_user_is_root()}")

            try:
                # Get the command method
                func = getattr(self, f'do_{cmd}', None)
                if func:
                    func(args)
                else:
                    # Try running it as an installed app
                    args_list = shlex.split(args) if args else []
                    if not self.km.run_program(cmd, args_list):
                        print(f"kos: command not found: {cmd}")
            finally:
                # Restore original user if necessary
                if original_user:
                    self.us.current_user = original_user
                    if self.us.current_user == "kaede":
                        self.us.users[self.us.current_user]["is_root"] = original_is_root

        except Exception as e:
            print(f"Error executing command: {str(e)}")

    def do_whoami(self, arg):
        """Display current user name
        Usage: whoami
        """
        if self.us.current_user:
            print(self.us.current_user)
        else:
            print("No user logged in")

    def do_su(self, arg):
        """Switch user
        Usage: su [username]
        Default username is kaede (root)
        """
        try:
            args = shlex.split(arg)
            username = args[0] if args else "kaede"

            # Get password unless switching to root as root
            password = None
            if not (self.us.current_user_is_root() and username == "kaede"):
                password = getpass.getpass()

            if self.us.switch_user(username, password):
                self.prompt = self.us.get_prompt()
            else:
                print("Authentication failed")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_kudo(self, arg):
        """Execute a command with root privileges
        Usage: kudo command
        """
        if not arg:
            print("Error: Command required")
            return

        if not self.us.can_sudo(self.us.current_user):
            print(f"{self.us.current_user} is not in the sudoers file")
            return

        # Get user's password
        password = getpass.getpass("[kudo] password for %s: " % self.us.current_user)
        if not self.us.verify_sudo_password(self.us.current_user, password):
            print("Sorry, try again.")
            return

        # Create sudo context and execute command
        context = CommandContext(self.us.current_user, is_sudo=True)

        # Parse command and arguments
        parts = shlex.split(arg)
        cmd = parts[0]
        args = ' '.join(parts[1:]) if len(parts) > 1 else ''

        self._execute_with_context(cmd, args, context)

    def do_ls(self, arg):
        """List directory contents with detailed information
        Usage: ls [-l] [-a] [path]
        -l: long format with permissions and details
        -a: show hidden files
        """
        try:
            args = shlex.split(arg) if arg else []
            show_hidden = '-a' in args
            long_format = '-l' in args

            # Remove flags from args
            path_args = [a for a in args if not a.startswith('-')]
            path = path_args[0] if path_args else "."

            # Get file list from filesystem
            logger.debug(f"Executing ls command for path: {path}")
            files = self.fs.list_directory(path, long_format)

            # Handle hidden files
            if not show_hidden and isinstance(files, list):
                files = [f for f in files if not f.startswith('.')]

            # Display results
            if Table and self.console:
                if long_format:
                    table = Table(show_header=True)
                    table.add_column("Permissions")
                    table.add_column("Owner")
                    table.add_column("Size")
                    table.add_column("Modified")
                    table.add_column("Name")
                    for entry in files:
                        table.add_row(
                            entry['perms'],
                            entry['owner'],
                            str(entry['size']),
                            entry['modified'],
                            entry['name']
                        )
                else:
                    table = Table.grid(padding=1)
                    table.add_column()
                    # Split files into chunks for better display
                    chunk_size = 4
                    chunks = [files[i:i + chunk_size] for i in range(0, len(files), chunk_size)]
                    for chunk in chunks:
                        table.add_row(*chunk)
                self.console.print(table)
            else:
                # Basic output
                if long_format:
                    for entry in files:
                        print(f"{entry['perms']} {entry['owner']} {entry['size']} {entry['modified']} {entry['name']}")
                else:
                    print("  ".join(files))

        except FileNotFound as e:
            print(f"ls: {str(e)}")
        except NotADirectory as e:
            print(f"ls: {str(e)}")
        except Exception as e:
            print(f"ls: {str(e)}")
            logger.error(f"Error in ls command: {str(e)}")

    def do_find(self, arg):
        """Find files in directory hierarchy
        Usage: find [path] [-name pattern] [-type f|d] [-size +|-n]
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("Error: Path required")
                return

            path = args[0]
            name_pattern = None
            type_filter = None
            size_filter = None

            i = 1
            while i < len(args):
                if args[i] == '-name' and i + 1 < len(args):
                    name_pattern = args[i + 1]
                    i += 2
                elif args[i] == '-type' and i + 1 < len(args):
                    type_filter = args[i + 1]
                    i += 2
                elif args[i] == '-size' and i + 1 < len(args):
                    size_filter = args[i + 1]
                    i += 2
                else:
                    i += 1

            def match_criteria(file_info):
                if name_pattern and not re.match(name_pattern.replace('*', '.*'), file_info['name']):
                    return False
                if type_filter == 'f' and file_info['type'] != 'file':
                    return False
                if type_filter == 'd' and file_info['type'] != 'dir':
                    return False
                if size_filter:
                    size_op = size_filter[0]
                    size_val = int(size_filter[1:])
                    if size_op == '+' and file_info['size'] <= size_val:
                        return False
                    if size_op == '-' and file_info['size'] >= size_val:
                        return False
                return True

            results = self.fs.find(path, match_criteria)
            for result in results:
                print(result)

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_grep(self, arg):
        """Search for patterns in files
        Usage: grep [-i] [-n] pattern [file...]
        -i: ignore case
        -n: show line numbers
        """
        try:
            args = shlex.split(arg)
            if len(args) < 2:
                print("Error: Pattern and file required")
                return

            ignore_case = '-i' in args
            show_lines = '-n' in args
            pattern = next(arg for arg in args if not arg.startswith('-'))
            files = [arg for arg in args if not arg.startswith('-') and arg != pattern]

            for file in files:
                content = self.fs.read_file(file)
                for i, line in enumerate(content.split('\n'), 1):
                    if (ignore_case and pattern.lower() in line.lower()) or \
                       (not ignore_case and pattern in line):
                        if show_lines:
                            print(f"{file}:{i}:{line}")
                        else:
                            print(f"{file}:{line}")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_chmod(self, arg):
        """Change file mode bits
        Usage: chmod mode file
        mode: octal (e.g., 755) or symbolic (e.g., u+x)
        """
        try:
            args = shlex.split(arg)
            if len(args) != 2:
                print("Error: Mode and file required")
                return

            mode, path = args
            self.fs.chmod(path, mode)

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_chown(self, arg):
        """Change file owner and group
        Usage: chown owner[:group] file
        """
        try:
            args = shlex.split(arg)
            if len(args) != 2:
                print("Error: Owner and file required")
                return

            owner, path = args
            uid = gid = None
            if ':' in owner:
                uid, gid = owner.split(':')
            else:
                uid = owner

            self.fs.chown(path, uid, gid)

        except Exception as e:
            print(f"Error: {str(e)}")

    # System Operations
    def do_ps(self, arg):
        """Report process status
        Usage: ps [-ef]
        """
        try:
            # Simulate process listing
            processes = [
                {"pid": 1, "user": "root", "start": "00:00", "cmd": "init"},
                {"pid": 2, "user": "root", "start": "00:00", "cmd": "kos_kernel"},
                {"pid": 100, "user": self.env_vars["USER"], "start": time.strftime("%H:%M"), "cmd": "kos_shell"}
            ]

            if Table and self.console:
                table = Table(show_header=True)
                table.add_column("PID")
                table.add_column("User") 
                table.add_column("Start")
                table.add_column("Command")

                for proc in processes:
                    table.add_row(
                        str(proc["pid"]),
                        proc["user"],
                        proc["start"],
                        proc["cmd"]
                    )
                self.console.print(table)
            else:
                # Fallback to basic output
                print("  PID USER     START   COMMAND")
                for proc in processes:
                    print(f"{proc['pid']:>5} {proc['user']:<8} {proc['start']} {proc['cmd']}")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_df(self, arg):
        """Report file system disk space usage
        Usage: df [-h]
        """
        try:
            args = shlex.split(arg) 
            human_readable = '-h' in args

            stats = self.fs.get_stats()

            # Format values
            if human_readable:
                size = f"{stats['total_size'] / (1024*1024):.1f}M"
                used = f"{stats['used_size'] / (1024*1024):.1f}M"
                avail = f"{stats['free_size'] / (1024*1024):.1f}M"
            else:
                size = str(stats['total_size'])
                used = str(stats['used_size'])
                avail = str(stats['free_size'])

            use_percent = f"{(stats['used_size'] / stats['total_size'] * 100):.1f}%"

            # Display results based on available capabilities
            if Table and self.console:
                table = Table(show_header=True)
                table.add_column("Filesystem")
                table.add_column("Size")
                table.add_column("Used") 
                table.add_column("Avail")
                table.add_column("Use%")
                table.add_column("Mounted on")

                table.add_row(
                    "kos_disk",
                    size,
                    used,
                    avail,
                    use_percent,
                    "/"
                )

                self.console.print(table)
            else:
                # Fallback to basic output
                print("Filesystem    Size   Used   Avail  Use%  Mounted on")
                print(f"{'kos_disk':<12} {size:>6} {used:>6} {avail:>6} {use_percent:>5}  /")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_top(self, arg):
        """Display system tasks
        Usage: top
        """
        try:
            while True:
                if self.console and hasattr(self.console, 'clear'):
                    self.console.clear()
                else:
                    print("\n" * 25)  # Simple screen clear
                    
                print(f"KOS top - {time.strftime('%H:%M:%S')}")
                print(f"Tasks: 3 total")
                print("\nCPU: 2% user, 1% system, 97% idle")
                print("Mem: 100M total, 10M used, 90M free")

                processes = [
                    {"pid": 1, "user": "root", "cpu": 0.1, "mem": 1.0, "cmd": "init"},
                    {"pid": 2, "user": "root", "cpu": 0.5, "mem": 2.0, "cmd": "kos_kernel"},
                    {"pid": 100, "user": self.env_vars["USER"], "cpu": 1.4, "mem": 7.0, "cmd": "kos_shell"}
                ]

                if Table and self.console:
                    table = Table(show_header=True)
                    table.add_column("PID")
                    table.add_column("USER")
                    table.add_column("%CPU")
                    table.add_column("%MEM")
                    table.add_column("Command")

                    for proc in processes:
                        table.add_row(
                            str(proc["pid"]),
                            proc["user"],
                            f"{proc['cpu']:.1f}",
                            f"{proc['mem']:.1f}",
                            proc["cmd"]
                        )
                    self.console.print(table)
                else:
                    # Basic table output
                    print("\nPID   USER     %CPU   %MEM   COMMAND")
                    print("-" * 45)
                    for proc in processes:
                        print(f"{proc['pid']:<6} {proc['user']:<8} {proc['cpu']:>5.1f} {proc['mem']:>6.1f}  {proc['cmd']}")

                time.sleep(2)  # Update every 2 seconds

        except KeyboardInterrupt:
            print("\nExiting top")
        except Exception as e:
            print(f"Error: {str(e)}")

    # Network Operations
    def do_ping(self, arg):
        """Send ICMP ECHO_REQUEST to network hosts
        Usage: ping [-c count] host
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("Error: Host required")
                return

            count = 4  # Default ping count
            if '-c' in args:
                c_index = args.index('-c')
                if c_index + 1 < len(args):
                    count = int(args[c_index + 1])
                    args.pop(c_index)
                    args.pop(c_index)

            host = args[0]
            print(f"PING {host}")

            for i in range(count):
                time.sleep(1)  # Simulate network delay
                print(f"64 bytes from {host}: icmp_seq={i+1} ttl=64 time={20+i}.{i*2} ms")

            print(f"\n--- {host} ping statistics ---")
            print(f"{count} packets transmitted, {count} received, 0% packet loss")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_netstat(self, arg):
        """Print network connections
        Usage: netstat [-a] [-n]
        """
        try:
            # Simulate network connections
            connections = [
                {"proto": "tcp", "local": "0.0.0.0:5000", "foreign": "0.0.0.0:*", "state": "LISTEN"},
                {"proto": "tcp", "local": "127.0.0.1:5000", "foreign": "127.0.0.1:54321", "state": "ESTABLISHED"}
            ]

            if Table and self.console:
                table = Table(show_header=True)
                table.add_column("Proto")
                table.add_column("Local Address")
                table.add_column("Foreign Address")
                table.add_column("State")

                for conn in connections:
                    table.add_row(
                        conn["proto"],
                        conn["local"],
                        conn["foreign"],
                        conn["state"]
                    )

                self.console.print(table)
            else:
                # Fallback to basic output
                print("Proto  Local Address         Foreign Address       State")
                for conn in connections:
                    print(f"{conn['proto']:<6} {conn['local']:<20} {conn['foreign']:<20} {conn['state']}")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_wget(self, arg):
        """Download files from the network
        Usage: wget URL
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("Error: URL required")
                return

            url = args[0]
            filename = url.split('/')[-1] or 'index.html'

            print(f"Connecting to {url}...")
            time.sleep(1)  # Simulate network delay
            print(f"200 OK")
            print(f"Saving to: {filename}")
            print(f"100% [...............................] {filename}")
            print("Download complete")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_curl(self, arg):
        """Transfer data with URLs
        Usage: curl [-I] URL
        -I: fetch headers only
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("Error: URL required")
                return

            headers_only = '-I' in args
            url = next((a for a in args if not a.startswith('-')), None)

            if not url:
                print("Error: URL required")
                return

            print(f"* Connecting to {url}...")
            time.sleep(0.5)  # Simulate network delay

            if headers_only:
                print("HTTP/1.1 200 OK")
                print("Server: KOS/1.0")
                print("Content-Type: text/html")
                print("Connection: keep-alive")
            else:
                print("HTTP/1.1 200 OK")
                print(f"* Connected to {url}")
                print("* Simulated response data would appear here")

        except Exception as e:
            print(f"Error: {str(e)}")

    # Text Processing
    def do_sed(self, arg):
        """Stream editor for filtering and transforming text
        Usage: sed 's/pattern/replacement/' [file]
        """
        try:
            args = shlex.split(arg)
            if len(args) < 1:
                print("Error: Expression required")
                return

            expression = args[0]
            file = args[1] if len(args) > 1 else None

            if not expression.startswith('s/'):
                print("Error: Only substitution expressions supported (s/pattern/replacement/)")
                return

            parts = expression[2:].split('/')
            if len(parts) < 2:
                print("Error: Invalid expression format")
                return

            pattern, replacement = parts[0], parts[1]

            if file:
                content = self.fs.read_file(file)
                modified = re.sub(pattern, replacement, content)
                print(modified)
            else:
                print("Reading from stdin not implemented")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_sort(self, arg):
        """Sort lines of text files
        Usage: sort [-r] [-n] [file]
        -r: reverse sort
        -n: numeric sort
        """
        try:
            args = shlex.split(arg)
            reverse = '-r' in args
            numeric = '-n' in args

            # Remove flags from args
            file_args = [a for a in args if not a.startswith('-')]
            file = file_args[0] if file_args else None

            if file:
                content = self.fs.read_file(file)
                lines = content.split('\n')

                if numeric:
                    lines.sort(key=lambda x: float(x) if x.strip().replace('.','').isdigit() else float('inf'), reverse=reverse)
                else:
                    lines.sort(reverse=reverse)

                for line in lines:
                    print(line)
            else:
                print("Reading from stdin not implemented")

        except Exception as e:
            print(f"Error: {str(e)}")

    # Application Management
    def do_kpm(self, arg):
        """KOS Package Manager (KPM)
        Usage: kpm <command> [options]
        Commands:
            update              Update package lists from repositories
            install <pkg>      Install a package
            remove <pkg>       Remove a package
            list              List installed packages
            search <query>     Search for packages
            add-repo <url>    Add a new repository
            remove-repo <url>  Remove a repository
        """
        try:
            args = shlex.split(arg)
            if not args:
                print(self.do_kpm.__doc__)
                return

            command = args[0]
            if command == "update":
                if self.km.update():
                    print("Package lists updated")
                else:
                    print("Failed to update package lists")
            elif command == "install" and len(args) > 1:
                if self.km.install(args[1]):
                    print(f"Successfully installed {args[1]}")
                else:
                    print(f"Failed to install {args[1]}")
            elif command == "remove" and len(args) > 1:
                if self.km.remove(args[1]):
                    print(f"Successfully removed {args[1]}")
                else:
                    print(f"Failed to remove {args[1]}")
            elif command == "list":
                self.km.list_packages() #Changed to list_packages
            elif command == "search" and len(args) > 1:
                results = self.km.search(args[1])
                if results:
                    print("\nSearch results:")
                    for pkg in results:
                        # Handle dictionary results from the updated search method
                        print(f"\n{pkg['name']} ({pkg['version']})")
                        print(f"  Description: {pkg['description']}")
                        print(f"  Author: {pkg['author']}")
                        if pkg.get('dependencies'):
                            deps = pkg.get('dependencies', [])
                            if deps:
                                print(f"  Dependencies: {', '.join(str(d) for d in deps)}")
                        if pkg.get('installed'):
                            print("  [Installed]")
                else:
                    print("No packages found")
            elif command == "add-repo" and len(args) > 1:
                repo_url = args[1] # Get the URL directly from args[1]
                        # url = args[2] if len(args) > 2 else f"https://{name}.kos-repo.org" # Remove this line, we don't need 'name' here

                if self.km.repo_config.add_repository(repo_url): # <--- Pass only repo_url
                    print(f"Added repository '{repo_url}'") # Update print statement to use repo_url
                else:
                    print(f"Failed to add repository '{repo_url}'") # Update print statement to use repo_url
            elif command == "remove-repo" and len(args) > 1:
                name = args[1]
                if self.km.repo_config.remove_repository(name):
                    print(f"Removed repository '{name}'")
                else:
                    print(f"Failed to remove repository '{name}'")
            elif command == "enable-repo" and len(args) > 1:
                name = args[1]
                if self.km.repo_config.enable_repository(name):
                    print(f"Enabled repository '{name}'")
                else:
                    print(f"Failed to enable repository '{name}'")
            elif command == "disable-repo" and len(args) > 1:
                name = args[1]
                if self.km.repo_config.disable_repository(name):
                    print(f"Disabled repository '{name}'")
                else:
                    print(f"Failed to disable repository '{name}'")
            else:
                print("Invalid command. Use: kapp help for usage information")
        except Exception as e:
            print(f"Error: {str(e)}")

    def do_exit(self, arg):
        """Exit the shell"""
        print("Goodbye!")
        return True

    def do_EOF(self, arg):
        """Exit on Ctrl-D"""
        print("\nGoodbye!")
        return True

    # Command completion
    def complete_cd(self, text, line, begidx, endidx):
        return self._complete_path(text)

    def complete_ls(self, text, line, begidx, endidx):
        return self._complete_path(text)

    def complete_cat(self, text, line, begidx, endidx):
        return self._complete_path(text)

    def complete_rm(self, text, line, begidx, endidx):
        return self._complete_path(text)

    def _complete_path(self, text):
        path = text.split('/')
        if len(path) == 1:
            options = self.fs.ls()
        else:
            try:
                parent_path = '/'.join(path[:-1])
                options = self.fs.ls(parent_path)
            except:
                return []
        return [opt for opt in options if opt.startswith(path[-1])]

    def do_tar(self, arg):
        """Create or extract tar archives
        Usage: tar -c|-x [-f archive] [files...]
        -c: create archive
        -x: extract archive
        -f: archive file
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("Error: Operation (-c|-x) required")
                return

            operation = None
            archive_file = None
            files = []

            i = 0
            while i < len(args):
                if args[i] == '-c':
                    operation = 'create'
                elif args[i] == '-x':
                    operation = 'extract'
                elif args[i] == '-f' and i + 1 < len(args):
                    archive_file = args[i + 1]
                    i += 1
                else:
                    files.append(args[i])
                i += 1

            if not operation or not archive_file:
                print("Error: Both operation and archive file (-f) required")
                return

            if operation == 'create':
                self.fs.create_tar(archive_file, files)
                print(f"Created archive {archive_file}")
            else:
                self.fs.extract_tar(archive_file)
                print(f"Extracted archive {archive_file}")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_mkdir(self, arg):
        """Create a directory
        Usage: mkdir directory_name
        """
        try:
            if not arg:
                print("mkdir: missing operand")
                return

            path = arg.strip()
            logger.debug(f"Creating directory: {path}")
            self.fs.mkdir(path)

        except FileNotFound as e:
            print(f"mkdir: {str(e)}")
        except NotADirectory as e:
            print(f"mkdir: {str(e)}")
        except FileSystemError as e:
            print(f"mkdir: {str(e)}")
        except Exception as e:
            print(f"mkdir: {str(e)}")
            logger.error(f"Error in mkdir command: {str(e)}")

    def do_gzip(self, arg):
        """Compress or decompress files
        Usage: gzip [-d] file
        -d: decompress
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("Error: File required")
                return

            decompress = '-d' in args
            files = [a for a in args if not a.startswith('-')]

            if not files:
                print("Error: File required")
                return

            for file in files:
                if decompress:
                    if not file.endswith('.gz'):
                        print(f"Error: {file} doesn't have .gz extension")
                        continue
                    output = file[:-3]
                    self.fs.gunzip_file(file, output)
                    print(f"Decompressed {file} to {output}")
                else:
                    output = file + '.gz'
                    self.fs.gzip_file(file, output)
                    print(f"Compressed {file} to {output}")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_diff(self, arg):
        """Compare files line by line
        Usage: diff [-u] file1 file2
        -u: unified format
        """
        try:
            args = shlex.split(arg)
            if len(args) < 2:
                print("Error: Two files required")
                return

            unified = '-u' in args
            files = [a for a in args if not a.startswith('-')]

            if len(files) != 2:
                print("Error: Exactly two files required")
                return

            content1 = self.fs.read_file(files[0]).split('\n')
            content2 = self.fs.read_file(files[1]).split('\n')

            if unified:
                # Generate unified diff format
                from difflib import unified_diff
                diff = list(unified_diff(content1, content2, fromfile=files[0], tofile=files[1]))
                print('\n'.join(diff))
            else:
                # Simple diff output
                from difflib import ndiff
                diff = list(ndiff(content1, content2))
                print('\n'.join(diff))

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_kill(self, arg):
        """Terminate processes
        Usage: kill [-9] pid
        -9: force terminate
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("Error: PID required")
                return

            force = '-9' in args
            pids = [int(a) for a in args if not a.startswith('-')]

            if not pids:
                print("Error: PID required")
                return

            for pid in pids:
                # Simulate process termination
                if pid in [1, 2]:  # Protected system processes
                    print(f"Error: Cannot terminate system process {pid}")
                else:
                    print(f"Process {pid} {'terminated' if force else 'requested to terminate'}")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_awk(self, arg):
        """Pattern scanning and text processing
        Usage: awk pattern [file]
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("Error: Pattern required")
                return

            pattern = args[0]
            file = args[1] if len(args) > 1 else None

            if file:
                content = self.fs.read_file(file)
                for line in content.split('\n'):
                    # Simple field splitting and pattern matching
                    fields = line.split()
                    if pattern.startswith('/') and pattern.endswith('/'):
                        # Regex pattern
                        if re.search(pattern[1:-1], line):
                            print(line)
                    elif pattern.startswith('{') and pattern.endswith('}'):
                        # Action block
                        # Basic implementation - print specific fields
                        try:
                            field_num = int(pattern[1:-1])
                            if len(fields) >= field_num:
                                print(fields[field_num - 1])
                        except ValueError:
                            print(line)
                    else:
                        print(line)
            else:
                print("Reading from stdin not implemented")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_head(self, arg):
        """Output the first part of files
        Usage: head [-n count] [file]
        """
        try:
            args = shlex.split(arg)
            lines = 10  # Default number of lines

            if '-n' in args:
                n_index = args.index('-n')
                if n_index + 1 < len(args):
                    lines = int(args[n_index + 1])
                    args.pop(n_index)
                    args.pop(n_index)

            file = args[0] if args else None

            if file:
                content = self.fs.read_file(file)
                print('\n'.join(content.split('\n')[:lines]))
            else:
                print("Reading from stdin not implemented")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_tail(self, arg):
        """Output the last part of files
        Usage: tail [-n count] [-f] [file]
        """
        try:
            args = shlex.split(arg)
            lines = 10  # Default number of lines
            follow = False

            if '-n' in args:
                n_index = args.index('-n')
                if n_index + 1 < len(args):
                    lines = int(args[n_index + 1])
                    args.pop(n_index)
                    args.pop(n_index)

            if '-f' in args:
                follow = True
                args.remove('-f')

            file = args[0] if args else None

            if file:
                content = self.fs.read_file(file)
                content_lines = content.split('\n')
                print('\n'.join(content_lines[-lines:]))

                if follow:
                    print("Following file updates (Ctrl+C to stop)...")
                    try:
                        while True:
                            time.sleep(1)
                            new_content = self.fs.read_file(file)
                            if new_content != content:
                                new_lines = new_content.split('\n')
                                print('\n'.join(new_lines[len(content_lines):]))
                                content = new_content
                                content_lines = new_lines
                    except KeyboardInterrupt:
                        print("\nStopped following file")
            else:
                print("Reading from stdin not implemented")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_uniq(self, arg):
        """Report or filter out repeated lines in a file
        Usage: uniq [-c] [-d] [file]
        -c: prefix lines with count
        -d: only print duplicate lines
        """
        try:
            args = shlex.split(arg)
            count = '-c' in args
            duplicates = '-d' in args

            file_args = [a for a in args if not a.startswith('-')]
            file = file_args[0] if file_args else None

            if file:
                content = self.fs.read_file(file)
                lines = content.split('\n')

                from collections import Counter
                line_counts = Counter(lines)

                for line, line_count in line_counts.items():
                    if duplicates and line_count == 1:
                        continue
                    if count:
                        print(f"{line_count:>7} {line}")
                    else:
                        print(line)
            else:
                print("Reading from stdin not implemented")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_cmp(self, arg):
        """Compare two files byte by byte"""
        try:
            args = shlex.split(arg)
            if len(args) != 2:
                print("Error: Two files are required.")
                return
            file1, file2 = args
            if self.fs.cmp(file1, file2):
                print(f"Files '{file1}' and '{file2}' are identical.")
            else:
                print(f"Files '{file1}' and '{file2}' are different.")
        except FileNotFoundError:
            print("Error: One or both of the files were not found.")
        except Exception as e:
            print(f"Error: {e}")


    def do_nice(self, arg):
        """Adjust the priority of a command"""
        try:
            args = shlex.split(arg)
            if len(args) != 2:
                print("Error: Incorrect number of arguments. Usage: nice <increment> <command>")
                return
            increment, command = args
            try:
                increment = int(increment)
                #Simulate nice command.  In a real system, this would adjust process priority.
                print(f"Command '{command}' will run with incremented niceness of {increment}")
            except ValueError:
                print("Error: Niceness increment must be an integer.")

        except Exception as e:
            print(f"Error: {e}")

    def do_man(self, arg):
        """Display manual pages
        Usage: man <topic>
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("Error: Topic required")
                print("\nAvailable topics:")
                for topic in self.man_system.list_topics():
                    print(f"  {topic}")
                return

            topic = args[0].lower()
            content = self.man_system.get_page(topic)

            if content:
                # Use a pager-like display
                lines = content.split('\n')
                page_size = 20
                current_line = 0

                while current_line < len(lines):
                    for i in range(current_line, min(current_line + page_size, len(lines))):
                        print(lines[i])

                    if current_line + page_size < len(lines):
                        response = input("Press ENTER for more, 'q' to quit: ")
                        if response.lower() == 'q':
                            break
                        current_line += page_size
                    else:
                        break
            else:
                print(f"No manual entry for {topic}")  # Fixed printprint typo

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_whoami(self, arg):
        """Display current user name
        Usage: whoami
        """
        print(self.us.current_user)

    def do_su(self, arg):
        """Switch user
        Usage: su [username]
        Default username is kaede (root)
        """
        try:
            args = shlex.split(arg)
            username = args[0] if args else "kaede"

            password = getpass.getpass()
            if self.us.switch_user(username, password):
                self.prompt = self.us.get_prompt()

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_hostname(self, arg):
        """Show or set system hostname
        Usage: hostname [new-hostname]
        """
        try:
            if not arg:
                print(self.us.hostname)
                return

            if not self.us.current_user_is_root():
                print("Permission denied: only root can change hostname")
                return

            self.us.set_hostname(arg)
            self.prompt = self.us.get_prompt()

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_useradd(self, arg):
        """Create a new user
        Usage: useradd username
        """
        try:
            if not self.us.current_user_is_root():
                print("Permission denied: only root can add users")
                return

            args = shlex.split(arg)
            if not args:
                print("Error: Username required")
                return

            username = args[0]
            password = getpass.getpass("Enter password: ")
            verify = getpass.getpass("Verify password: ")

            if password != verify:
                print("Passwords do not match")
                return

            if self.us.add_user(username, password):
                print(f"User {username} created successfully")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_userdel(self, arg):
        """Delete a user
        Usage: userdel username
        """
        try:
            if not self.us.current_user_is_root():
                print("Permission denied: only root can delete users")
                return

            args = shlex.split(arg)
            if not args:
                print("Error: Username required")
                return

            username = args[0]
            if username == "kaede":
                print("Cannot delete root user")
                return

            if self.us.delete_user(username):
                print(f"User {username} deleted successfully")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_groups(self, arg):
        """Show group memberships
        Usage: groups [username]
        """
        try:
            args = shlex.split(arg)
            username = args[0] if args else self.us.current_user
            groups = self.us.get_groups(username)
            print(" ".join(groups))

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_id(self, arg):
        """Print user and group IDs
        Usage: id [username]
        """
        try:
            args = shlex.split(arg)
            username = args[0] if args else self.us.current_user
            info = self.us.get_user_info(username)

            print(f"uid={info['uid']}({username}) gid={info['gid']}({info['groups'][0]}) groups={','.join(str(info['gid']) + '(' + g + ')' for g in info['groups'])}")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_cd(self, arg):
        """Change directory
        Usage: cd [directory]
        """
        try:
            if not arg:
                # Change to home directory if no argument
                arg = self.env_vars["HOME"]
            self.fs.cd(arg)
            self.prompt = self.us.get_prompt()  # Update prompt with new path
        except Exception as e:
            print(f"Error: {str(e)}")

    def do_pwd(self, arg):
        """Print working directory
        Usage: pwd
        """
        print(self.fs.pwd())

    def do_mkdir(self, arg):
        """Create directory
        Usage: mkdir [-p] directory
        -p: create parent directories as needed
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("Error: Directory name required")
                return

            create_parents = '-p' in args
            dirs = [d for d in args if not d.startswith('-')]

            for dir_name in dirs:
                self.fs.mkdir(dir_name, create_parents)

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_touch(self, arg):
        """Create empty file
        Usage: touch file [file2 ...]
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("Error: File name required")
                return

            for file in args:
                self.fs.touch(file)

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_cat(self, arg):
        """Print file contents
        Usage: cat file [file2 ...]
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("Error: File name required")
                return

            for file in args:
                content = self.fs.read_file(file)
                print(content)

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_cp(self, arg):
        """Copy files
        Usage: cp [-r] source destination
        -r: copy directories recursively
        """
        try:
            args = shlex.split(arg)
            if len(args) < 2:
                print("Error: Source and destination required")
                return

            recursive = '-r' in args
            files = [f for f in args if not f.startswith('-')]

            if len(files) != 2:
                print("Error: Need exactly two paths")
                return

            source, dest = files
            self.fs.cp(source, dest, recursive)

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_mv(self, arg):
        """Move/rename files
        Usage: mv source destination
        """
        try:
            args = shlex.split(arg)
            if len(args) != 2:
                print("Error: Source and destination required")
                return

            source, dest = args
            self.fs.mv(source, dest)

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_rm(self, arg):
        """Remove files or directories
        Usage: rm [-r] [-f] file [file2 ...]
        -r: remove directories and their contents recursively
        -f: force removal without confirmation
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("Error: File name required")
                return

            recursive = '-r' in args or '-rf' in args
            force = '-f' in args or '-rf' in args
            files = [f for f in args if not f.startswith('-')]

            for file in files:
                if not force and self.fs.exists(file):
                    response = input(f"Remove {file}? [y/N] ")
                    if response.lower() != 'y':
                        continue
                self.fs.rm(file, recursive)

        except Exception as e:
            print(f"Error: {str(e)}")

    def default(self, line):
        """Handle unknown commands by checking if they're installed apps"""
        try:
            # Split command and arguments
            parts = shlex.split(line)
            if not parts:
                return False

            cmd = parts[0]
            args = parts[1:] if len(parts) > 1 else []

            # Check if it's an installed app
            if self.km.run_program(cmd, args):
                return True

            # Not an app, show error
            print(f"kos: command not found: {cmd}")
            return False

        except Exception as e:
            print(f"Error: {str(e)}")
            return False

    def get_names(self):
        """Get list of command names - overridden to include installed apps"""
        base_commands = super().get_names()

        # Add installed apps to command list
        installed_apps = [pkg.name for pkg in self.km.package_db.list_installed()]

        return base_commands + installed_apps

    def complete_default(self, text, line, begidx, endidx):
        """Provide completion for installed apps"""
        apps = [pkg.name for pkg in self.km.package_db.list_installed()]
        return [app for app in apps if app.startswith(text)]

    def do_kudo(self, arg):
        """Execute a command with root privileges
        Usage: kudo command
        """
        try:
            if not arg:
                print("Error: Command required")
                return

            if not self.us.can_sudo(self.us.current_user):
                print("User is not in the sudoers file")
                return

            # Get user's password
            password = getpass.getpass("[kudo] password for %s: " % self.us.current_user)
            if not self.us.verify_sudo_password(self.us.current_user, password):
                print("Sorry, try again.")
                return

            # Save current user
            original_user = self.us.current_user

            try:
                # Temporarily switch to root
                self.us.current_user = "kaede"

                # Execute the command
                line = arg.strip()
                if ' ' in line:
                    cmd, args = line.split(' ', 1)
                else:
                    cmd, args = line, ''

                func = getattr(self, f'do_{cmd}', None)
                if func:
                    func(args)
                else:
                    self.default(line)

            finally:
                # Restore original user
                self.us.current_user = original_user

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_help(self, arg):
        """List available commands"""
        if arg:
            # Get help for specific command
            super().do_help(arg)
            return

        print("KOS Command Reference\n")
        for category, cmds in self.command_categories.items():
            print(f"\n{category}:")
            for cmd in cmds:
                # Get the first line of the command's docstring
                doc = getattr(self, f"do_{cmd}").__doc__ or ""
                brief = doc.split('\n')[0]
                print(f"  {cmd:<12} {brief}")

        print("\nFor detailed help:\n  help <command>  Show detailed help for a command")
        print("  man <topic>    Show manual page for a topic")

    def precmd(self, line):
        """Pre-command hook for history and alias handling"""
        if line:
            # Handle aliases
            parts = line.split()
            if parts and parts[0] in self.aliases:
                line = self.aliases[parts[0]] + ' ' + ' '.join(parts[1:])

            # Add to history
            if len(self.cmd_history) >= self.history_limit:
                self.cmd_history.pop(0)
            self.cmd_history.append(line)

        return line

    def do_history(self, arg):
        """Display command history
        Usage: history [n]
        n: number of commands to show (default: all)
        """
        try:
            args = shlex.split(arg)
            n = int(args[0]) if args else len(self.cmd_history)

            for i, cmd in enumerate(self.cmd_history[-n:], 1):
                print(f"{i:5d}  {cmd}")
        except Exception as e:
            print(f"Error: {str(e)}")

    def do_alias(self, arg):
        """Define or display aliases
        Usage: alias [name[=value]]
        """
        try:
            if not arg:
                for name, value in self.aliases.items():
                    print(f"alias {name}='{value}'")
                return

            if '=' in arg:
                name, value = arg.split('=', 1)
                name = name.strip()
                value = value.strip().strip("'\"")
                self.aliases[name] = value
                print(f"Alias '{name}' set to '{value}'")
            else:
                name = arg.strip()
                if name in self.aliases:
                    print(f"alias {name}='{self.aliases[name]}'")
                else:
                    print(f"No alias named '{name}'")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_clear(self, arg):
        """Clear the terminal screen
        Usage: clear
        """
        self.console.clear()

    def do_whoami(self, arg):
        """Print effective user name
        Usage: whoami
        """
        print(self.us.current_user)

    def do_hostname(self, arg):
        """Show or set system hostname
        Usage: hostname [new-hostname]
        """
        try:
            args = shlex.split(arg)
            if not args:
                print(self.us.hostname)
                return

            if not self.us.current_user_is_root():
                print("Permission denied: only root can set hostname")
                return

            self.us.set_hostname(args[0])
            self.prompt = self.us.get_prompt()

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_su(self, arg):
        """Switch user
        Usage: su [username]
        """
        try:
            args = shlex.split(arg)
            username = args[0] if args else "kaede"

            if username == self.us.current_user:
                return

            if not self.us.current_user_is_root():
                password = getpass.getpass()
                if not self.us.switch_user(username, password):
                    print("Authentication failed")
                    return
            else:
                if not self.us.switch_user(username):
                    print(f"User {username} does not exist")
                    return

            self.prompt = self.us.get_prompt()
            self.env_vars["USER"] = username
            self.env_vars["HOME"] = self.us.get_user_info().get("home", f"/home/{username}")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_useradd(self, arg):
        """Create a new user
        Usage: useradd [-G groups] username
        """
        try:
            if not self.us.current_user_is_root():
                print("Permission denied: only root can add users")
                return

            args = shlex.split(arg)
            if not args:
                print("Error: Username required")
                return

            groups = []
            username = args[-1]

            if "-G" in args:
                idx = args.index("-G")
                if idx + 1 < len(args):
                    groups = args[idx + 1].split(',')

            password = getpass.getpass("Enter password: ")
            verify = getpass.getpass("Verify password: ")

            if password != verify:
                print("Passwords do not match")
                return

            self.us.add_user(username, password, groups)
            print(f"User {username} created successfully")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_userdel(self, arg):
        """Delete a user
        Usage: userdel [-r] username
        """
        try:
            if not self.us.current_user_is_root():
                print("Permission denied: only root can delete users")
                return

            args = shlex.split(arg)
            if not args:
                print("Error: Username required")
                return

            remove_home = "-r" in args
            username = args[-1]

            self.us.delete_user(username, remove_home)
            print(f"User {username} deleted successfully")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_groups(self, arg):
        """Print group memberships
        Usage: groups [username]
        """
        try:
            args = shlex.split(arg)
            username = args[0] if args else self.us.current_user

            groups = self.us.get_groups(username)
            print(f"{username} : {' '.join(groups)}")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_id(self, arg):
        """Print user and group information
        Usage: id [username]
        """
        try:
            args = shlex.split(arg)
            username = args[0] if args else self.us.current_user

            info = self.us.get_user_info(username)
            print(f"uid={info['uid']}({username}) gid={info['gid']}({info['groups'][0]}) groups={','.join(info['groups'])}")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_cd(self, arg):
        """Change directory
        Usage: cd [directory]
        """
        try:
            if not arg:
                # Change to home directory if no argument
                arg = self.env_vars["HOME"]
            self.fs.cd(arg)
            self.prompt = self.us.get_prompt()  # Update prompt with new path
        except Exception as e:
            print(f"Error: {str(e)}")

    def do_pwd(self, arg):
        """Print working directory
        Usage: pwd
        """
        print(self.fs.pwd())

    def do_mkdir(self, arg):
        """Create directory
        Usage: mkdir [-p] directory
        -p: create parent directories as needed
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("Error: Directory name required")
                return

            create_parents = '-p' in args
            dirs = [d for d in args if not d.startswith('-')]

            for dir_name in dirs:
                self.fs.mkdir(dir_name, create_parents)

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_touch(self, arg):
        """Create empty file
        Usage: touch file [file2 ...]
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("Error: File name required")
                return

            for file in args:
                self.fs.touch(file)

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_cat(self, arg):
        """Print file contents
        Usage: cat file [file2 ...]
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("Error: File name required")
                return

            for file in args:
                content = self.fs.read_file(file)
                print(content)

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_cp(self, arg):
        """Copy files
        Usage: cp [-r] source destination
        -r: copy directories recursively
        """
        try:
            args = shlex.split(arg)
            if len(args) < 2:
                print("Error: Source and destination required")
                return

            recursive = '-r' in args
            files = [f for f in args if not f.startswith('-')]

            if len(files) != 2:
                print("Error: Need exactly two paths")
                return

            source, dest = files
            self.fs.cp(source, dest, recursive)

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_mv(self, arg):
        """Move/rename files
        Usage: mv source destination
        """
        try:
            args = shlex.split(arg)
            if len(args) != 2:
                print("Error: Source and destination required")
                return

            source, dest = args
            self.fs.mv(source, dest)

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_rm(self, arg):
        """Remove files or directories
        Usage: rm [-r] [-f] file [file2 ...]
        -r: remove directories and their contents recursively
        -f: force removal without confirmation
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("Error: File name required")
                return

            recursive = '-r' in args or '-rf' in args
            force = '-f' in args or '-rf' in args
            files = [f for f in args if not f.startswith('-')]

            for file in files:
                if not force and self.fs.exists(file):
                    response = input(f"Remove {file}? [y/N] ")
                    if response.lower() != 'y':
                        continue
                self.fs.rm(file, recursive)

        except Exception as e:
            print(f"Error: {str(e)}")

    def default(self, line):
        """Handle unknown commands by checking if they're installed apps"""
        try:
            # Split command and arguments
            parts = shlex.split(line)
            if not parts:
                return False

            cmd = parts[0]
            args = parts[1:] if len(parts) > 1 else []

            # Check if it's an installed app
            if self.km.run_program(cmd, args):
                return True

            # Not an app, show error
            print(f"kos: command not found: {cmd}")
            return False

        except Exception as e:
            print(f"Error: {str(e)}")
            return False

    def get_names(self):
        """Get list of command names - overridden to include installed apps"""
        base_commands = super().get_names()

        # Add installed apps to command list
        installed_apps = [pkg.name for pkg in self.km.package_db.list_installed()]

        return base_commands + installed_apps

    def complete_default(self, text, line, begidx, endidx):
        """Provide completion for installed apps"""
        apps = [pkg.name for pkg in self.km.package_db.list_installed()]
        return [app for app in apps if app.startswith(text)]

    def do_kudo(self, arg):
        """Execute a command with root privileges
        Usage: kudo command
        """
        try:
            if not arg:
                print("Error: Command required")
                return

            if not self.us.can_sudo(self.us.current_user):
                print("User is not in the sudoers file")
                return

            # Get user's password
            password = getpass.getpass("[kudo] password for %s: " % self.us.current_user)
            if not self.us.verify_sudo_password(self.us.current_user, password):
                print("Sorry, try again.")
                return

            # Save current user
            original_user = self.us.current_user

            try:
                # Temporarily switch to root
                self.us.current_user = "kaede"

                # Execute the command
                line = arg.strip()
                if ' ' in line:
                    cmd, args = line.split(' ', 1)
                else:
                    cmd, args = line, ''

                func = getattr(self, f'do_{cmd}', None)
                if func:
                    func(args)
                else:
                    self.default(line)

            finally:
                # Restore original user
                self.us.current_user = original_user

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_help(self, arg):
        """List available commands"""
        if arg:
            # Get help for specific command
            super().do_help(arg)
            return

        print("KOS Command Reference\n")
        for category, cmds in self.command_categories.items():
            print(f"\n{category}:")
            for cmd in cmds:
                # Get the first line of the command's docstring
                doc = getattr(self, f"do_{cmd}").__doc__ or ""
                brief = doc.split('\n')[0]
                print(f"  {cmd:<12} {brief}")

        print("\nFor detailed help:\n  help <command>  Show detailed help for a command")
        print("  man <topic>    Show manual page for a topic")

    def precmd(self, line):
        """Pre-command hook for history and alias handling"""
        if line:
            # Handle aliases
            parts = line.split()
            if parts and parts[0] in self.aliases:
                line = self.aliases[parts[0]] + ' ' + ' '.join(parts[1:])

            # Add to history
            if len(self.cmd_history) >= self.history_limit:
                self.cmd_history.pop(0)
            self.cmd_history.append(line)

        return line

    def do_history(self, arg):
        """Display command history
        Usage: history [n]
        n: number of commands to show (default: all)
        """
        try:
            args = shlex.split(arg)
            n = int(args[0]) if args else len(self.cmd_history)

            for i, cmd in enumerate(self.cmd_history[-n:], 1):
                print(f"{i:5d}  {cmd}")
        except Exception as e:
            print(f"Error: {str(e)}")

    def do_alias(self, arg):
        """Define or display aliases
        Usage: alias [name[=value]]
        """
        try:
            if not arg:
                for name, value in self.aliases.items():
                    print(f"alias {name}='{value}'")
                return

            if '=' in arg:
                name, value = arg.split('=', 1)
                name = name.strip()
                value = value.strip().strip("'\"")
                self.aliases[name] = value
                print(f"Alias '{name}' set to '{value}'")
            else:
                name = arg.strip()
                if name in self.aliases:
                    print(f"alias {name}='{self.aliases[name]}'")
                else:
                    print(f"No alias named '{name}'")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_clear(self, arg):
        """Clear the terminal screen
        Usage: clear
        """
        self.console.clear()

    def do_whoami(self, arg):
        """Print effective user name
        Usage: whoami
        """
        print(self.us.current_user)

    def do_hostname(self, arg):
        """Show or set system hostname
        Usage: hostname [new-hostname]
        """
        try:
            args = shlex.split(arg)
            if not args:
                print(self.us.hostname)
                return

            if not self.us.current_user_is_root():
                print("Permission denied: only root can set hostname")
                return

            self.us.set_hostname(args[0])
            self.prompt = self.us.get_prompt()

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_su(self, arg):
        """Switch user
        Usage: su [username]
        """
        try:
            args = shlex.split(arg)
            username = args[0] if args else "kaede"

            if username == self.us.current_user:
                return

            if not self.us.current_user_is_root():
                password = getpass.getpass()
                if not self.us.switch_user(username, password):
                    print("Authentication failed")
                    return
            else:
                if not self.us.switch_user(username):
                    print(f"User {username} does not exist")
                    return

            self.prompt = self.us.get_prompt()
            self.env_vars["USER"] = username
            self.env_vars["HOME"] = self.us.get_user_info().get("home", f"/home/{username}")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_useradd(self, arg):
        """Create a new user
        Usage: useradd [-G groups] username
        """
        try:
            if not self.us.current_user_is_root():
                print("Permission denied: only root can add users")
                return

            args = shlex.split(arg)
            if not args:
                print("Error: Username required")
                return

            groups = []
            username = args[-1]

            if "-G" in args:
                idx = args.index("-G")
                if idx + 1 < len(args):
                    groups = args[idx + 1].split(',')

            password = getpass.getpass("Enter password: ")
            verify = getpass.getpass("Verify password: ")

            if password != verify:
                print("Passwords do not match")
                return

            self.us.add_user(username, password, groups)
            print(f"User {username} created successfully")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_userdel(self, arg):
        """Delete a user
        Usage: userdel [-r] username
        """
        try:
            if not self.us.current_user_is_root():
                print("Permission denied: only root can delete users")
                return

            args = shlex.split(arg)
            if not args:
                print("Error: Username required")
                return

            remove_home = "-r" in args
            username = args[-1]

            self.us.delete_user(username, remove_home)
            print(f"User {username} deleted successfully")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_groups(self, arg):
        """Print group memberships
        Usage: groups [username]
        """
        try:
            args = shlex.split(arg)
            username = args[0] if args else self.us.current_user

            groups = self.us.get_groups(username)
            print(f"{username} : {' '.join(groups)}")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_id(self, arg):
        """Print user and group information
        Usage: id [username]
        """
        try:
            args = shlex.split(arg)
            username = args[0] if args else self.us.current_user

            info = self.us.get_user_info(username)
            print(f"uid={info['uid']}({username}) gid={info['gid']}({info['groups'][0]}) groups={','.join(info['groups'])}")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_cd(self, arg):
        """Change directory
        Usage: cd [directory]
        """
        try:
            if not arg:
                # Change to home directory if no argument
                arg = self.env_vars["HOME"]
            self.fs.cd(arg)
            self.prompt = self.us.get_prompt()  # Update prompt with new path
        except Exception as e:
            print(f"Error: {str(e)}")

    def do_pwd(self, arg):
        """Print working directory
        Usage: pwd
        """
        print(self.fs.pwd())

    def do_mkdir(self, arg):
        """Create directory
        Usage: mkdir [-p] directory
        -p: create parent directories as needed
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("Error: Directory name required")
                return

            create_parents = '-p' in args
            dirs = [d for d in args if not d.startswith('-')]

            for dir_name in dirs:
                self.fs.mkdir(dir_name, create_parents)

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_touch(self, arg):
        """Create empty file
        Usage: touch file [file2 ...]
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("Error: File name required")
                return

            for file in args:
                self.fs.touch(file)

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_cat(self, arg):
        """Print file contents
        Usage: cat file [file2 ...]
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("Error: File name required")
                return

            for file in args:
                content = self.fs.read_file(file)
                print(content)

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_cp(self, arg):
        """Copy files
        Usage: cp [-r] source destination
        -r: copy directories recursively
        """
        try:
            args = shlex.split(arg)
            if len(args) < 2:
                print("Error: Source and destination required")
                return

            recursive = '-r' in args
            files = [f for f in args if not f.startswith('-')]

            if len(files) != 2:
                print("Error: Need exactly two paths")
                return

            source, dest = files
            self.fs.cp(source, dest, recursive)

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_mv(self, arg):
        """Move/rename files
        Usage: mv source destination
        """
        try:
            args = shlex.split(arg)
            if len(args) != 2:
                print("Error: Source and destination required")
                return

            source, dest = args
            self.fs.mv(source, dest)

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_rm(self, arg):
        """Remove files or directories
        Usage: rm [-r] [-f] file [file2 ...]
        -r: remove directories and their contents recursively
        -f: force removal without confirmation
        """
        try:
            args = shlex.split(arg)
            if not args:
                print("Error: File name required")
                return

            recursive = '-r' in args or '-rf' in args
            force = '-f' in args or '-rf' in args
            files = [f for f in args if not f.startswith('-')]

            for file in files:
                if not force and self.fs.exists(file):
                    response = input(f"Remove {file}? [y/N] ")
                    if response.lower() != 'y':
                        continue
                self.fs.rm(file, recursive)

        except Exception as e:
            print(f"Error: {str(e)}")

    def default(self, line):
        """Handle unknown commands by checking if they're installed apps"""
        try:
            # Split command and arguments
            parts = shlex.split(line)
            if not parts:
                return False

            cmd = parts[0]
            args = parts[1:] if len(parts) > 1 else []

            # Check if it's an installed app
            if self.km.run_program(cmd, args):
                return True

            # Not an app, show error
            print(f"kos: command not found: {cmd}")
            return False

        except Exception as e:
            print(f"Error: {str(e)}")
            return False

    def get_names(self):
        """Get list of command names - overridden to include installed apps"""
        base_commands = super().get_names()

        # Add installed apps to command list
        installed_apps = [pkg.name for pkg in self.km.package_db.list_installed()]

        return base_commands + installed_apps

    def complete_default(self, text, line, begidx, endidx):
        """Provide completion for installed apps"""
        apps = [pkg.name for pkg in self.km.package_db.list_installed()]
        return [app for app in apps if app.startswith(text)]

    def do_kudo(self, arg):
        """Execute a command with root privileges
        Usage: kudo command
        """
        try:
            if not arg:
                print("Error: Command required")
                return

            if not self.us.can_sudo(self.us.current_user):
                print("User is not in the sudoers file")
                return

            # Get user's password
            password = getpass.getpass("[kudo] password for %s: " % self.us.current_user)
            if not self.us.verify_sudo_password(self.us.current_user, password):
                print("Sorry, try again.")
                return

            # Save current user
            original_user = self.us.current_user

            try:
                # Temporarily switch to root
                self.us.current_user = "kaede"

                # Execute the command
                line = arg.strip()
                if ' ' in line:
                    cmd, args = line.split(' ', 1)
                else:
                    cmd, args = line, ''

                func = getattr(self, f'do_{cmd}', None)
                if func:
                    func(args)
                else:
                    self.default(line)

            finally:
                # Restore original user
                self.us.current_user = original_user

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_help(self, arg):
        """List available commands"""
        if arg:
            # Get help for specific command
            super().do_help(arg)
            return

        print("KOS Command Reference\n")
        for category, cmds in self.command_categories.items():
            print(f"\n{category}:")
            for cmd in cmds:
                # Get the first line of the command's docstring
                doc = getattr(self, f"do_{cmd}").__doc__ or ""
                brief = doc.split('\n')[0]
                print(f"  {cmd:<12} {brief}")

        print("\nFor detailed help:\n  help <command>  Show detailed help for a command")
        print("  man <topic>    Show manual page for a topic")

    def precmd(self, line):
        """Pre-command hook for history and alias handling"""
        if line:
            # Handle aliases
            parts = line.split()
            if parts and parts[0] in self.aliases:
                line = self.aliases[parts[0]] + ' ' + ' '.join(parts[1:])

            # Add to history
            if len(self.cmd_history) >= self.history_limit:
                self.cmd_history.pop(0)
            self.cmd_history.append(line)

        return line

    def do_history(self, arg):
        """Display command history
        Usage: history [n]
        n: number of commands to show (default: all)
        """
        try:
            args = shlex.split(arg)
            n = int(args[0]) if args else len(self.cmd_history)

            for i, cmd in enumerate(self.cmd_history[-n:], 1):
                print(f"{i:5d}  {cmd}")
        except Exception as e:
            print(f"Error: {str(e)}")

    def do_alias(self, arg):
        """Define or display aliases
        Usage: alias [name[=value]]
        """
        try:
            if not arg:
                for name, value in self.aliases.items():
                    print(f"alias {name}='{value}'")
                return

            if '=' in arg:
                name, value = arg.split('=', 1)
                name = name.strip()
                value = value.strip().strip("'\"")
                self.aliases[name] = value
                print(f"Alias '{name}' set to '{value}'")
            else:
                name = arg.strip()
                if name in self.aliases:
                    print(f"alias {name}='{self.aliases[name]}'")
                else:
                    print(f"No alias named '{name}'")

        except Exception as e:
            print(f"Error: {str(e)}")

    def do_clear(self, arg):
        """Clear the terminal screen
        Usage: clear
        """
        self.console.clear()

    # Kaede language commands
    def do_kaede(self, arg):
        """Execute Kaede code or enter Kaede REPL"""
        if self.kaede_commands:
            return self.kaede_commands.do_kaede(arg)
        else:
            print("Kaede language not available")

    def do_kaedeinfo(self, arg):
        """Show information about Kaede language and runtime"""
        if self.kaede_commands:
            return self.kaede_commands.do_kaedeinfo(arg)
        else:
            print("Kaede language not available")

    def do_kaedeproject(self, arg):
        """Manage Kaede projects"""
        if self.kaede_commands:
            return self.kaede_commands.do_kaedeproject(arg)
        else:
            print("Kaede language not available")
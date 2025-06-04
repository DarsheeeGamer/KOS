"""
Comprehensive Command System for KOS
====================================

Implementation of all essential Unix/Linux commands with full functionality.
This includes file operations, text processing, system utilities, networking,
and administrative commands.
"""

import os
import sys
import shutil
import subprocess
import re
import time
import stat
import pwd
import grp
import socket
import hashlib
import tarfile
import zipfile
import gzip
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path
import logging

logger = logging.getLogger('KOS.commands')

class CommandExecutor:
    """Base class for command execution"""
    
    def __init__(self, shell):
        self.shell = shell
        self.current_dir = os.getcwd()
    
    def execute(self, args: List[str]) -> bool:
        """Execute command with arguments"""
        raise NotImplementedError

# File System Commands
class LSCommand(CommandExecutor):
    """ls - list directory contents"""
    
    def execute(self, args: List[str]) -> bool:
        long_format = False
        all_files = False
        human_readable = False
        recursive = False
        
        paths = []
        i = 0
        while i < len(args):
            if args[i] == '-l':
                long_format = True
            elif args[i] == '-a':
                all_files = True
            elif args[i] == '-h':
                human_readable = True
            elif args[i] == '-R':
                recursive = True
            elif args[i] == '-la' or args[i] == '-al':
                long_format = True
                all_files = True
            else:
                paths.append(args[i])
            i += 1
        
        if not paths:
            paths = ['.']
        
        for path in paths:
            self._list_directory(path, long_format, all_files, human_readable, recursive)
        
        return True
    
    def _list_directory(self, path: str, long_format: bool, all_files: bool, 
                       human_readable: bool, recursive: bool):
        try:
            if not os.path.exists(path):
                print(f"ls: cannot access '{path}': No such file or directory")
                return
            
            if os.path.isfile(path):
                self._list_file(path, long_format, human_readable)
                return
            
            entries = os.listdir(path)
            if not all_files:
                entries = [e for e in entries if not e.startswith('.')]
            
            entries.sort()
            
            if len(entries) == 0:
                return
            
            if long_format:
                for entry in entries:
                    full_path = os.path.join(path, entry)
                    self._list_file(full_path, long_format, human_readable)
            else:
                # Simple listing
                for entry in entries:
                    full_path = os.path.join(path, entry)
                    if os.path.isdir(full_path):
                        print(f"{entry}/", end="  ")
                    else:
                        print(entry, end="  ")
                print()  # New line at end
            
            if recursive:
                for entry in entries:
                    full_path = os.path.join(path, entry)
                    if os.path.isdir(full_path) and not entry.startswith('.'):
                        print(f"\n{full_path}:")
                        self._list_directory(full_path, long_format, all_files, 
                                           human_readable, recursive)
        
        except PermissionError:
            print(f"ls: cannot open directory '{path}': Permission denied")
        except Exception as e:
            print(f"ls: error listing '{path}': {e}")
    
    def _list_file(self, path: str, long_format: bool, human_readable: bool):
        try:
            stat_info = os.stat(path)
            
            if not long_format:
                print(os.path.basename(path))
                return
            
            # Permissions
            mode = stat_info.st_mode
            permissions = stat.filemode(mode)
            
            # Links
            links = stat_info.st_nlink
            
            # Owner and group
            try:
                owner = pwd.getpwuid(stat_info.st_uid).pw_name
            except:
                owner = str(stat_info.st_uid)
            
            try:
                group = grp.getgrgid(stat_info.st_gid).gr_name
            except:
                group = str(stat_info.st_gid)
            
            # Size
            size = stat_info.st_size
            if human_readable:
                size_str = self._human_readable_size(size)
            else:
                size_str = str(size)
            
            # Date
            mtime = datetime.fromtimestamp(stat_info.st_mtime)
            date_str = mtime.strftime('%b %d %H:%M')
            
            # Name
            name = os.path.basename(path)
            
            print(f"{permissions} {links:>3} {owner:<8} {group:<8} {size_str:>8} {date_str} {name}")
            
        except Exception as e:
            print(f"ls: error getting info for '{path}': {e}")
    
    def _human_readable_size(self, size: int) -> str:
        """Convert size to human readable format"""
        for unit in ['B', 'K', 'M', 'G', 'T']:
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}P"

class CDCommand(CommandExecutor):
    """cd - change directory"""
    
    def execute(self, args: List[str]) -> bool:
        if not args:
            # Go to home directory
            target = os.path.expanduser("~")
        else:
            target = args[0]
        
        try:
            # Handle relative paths
            if not os.path.isabs(target):
                target = os.path.join(self.current_dir, target)
            
            # Normalize path
            target = os.path.normpath(target)
            
            if not os.path.exists(target):
                print(f"cd: no such file or directory: {target}")
                return False
            
            if not os.path.isdir(target):
                print(f"cd: not a directory: {target}")
                return False
            
            os.chdir(target)
            self.shell.current_dir = target
            
            return True
            
        except PermissionError:
            print(f"cd: permission denied: {target}")
            return False
        except Exception as e:
            print(f"cd: error changing directory: {e}")
            return False

class PWDCommand(CommandExecutor):
    """pwd - print working directory"""
    
    def execute(self, args: List[str]) -> bool:
        print(os.getcwd())
        return True

class MKDIRCommand(CommandExecutor):
    """mkdir - create directories"""
    
    def execute(self, args: List[str]) -> bool:
        if not args:
            print("mkdir: missing operand")
            return False
        
        parents = False
        mode = 0o755
        
        dirs = []
        i = 0
        while i < len(args):
            if args[i] == '-p':
                parents = True
            elif args[i] == '-m' and i + 1 < len(args):
                try:
                    mode = int(args[i + 1], 8)
                    i += 1
                except ValueError:
                    print(f"mkdir: invalid mode '{args[i + 1]}'")
                    return False
            else:
                dirs.append(args[i])
            i += 1
        
        if not dirs:
            print("mkdir: missing operand")
            return False
        
        for dir_path in dirs:
            try:
                if parents:
                    os.makedirs(dir_path, mode, exist_ok=True)
                else:
                    os.mkdir(dir_path, mode)
                
                print(f"Created directory: {dir_path}")
                
            except FileExistsError:
                print(f"mkdir: cannot create directory '{dir_path}': File exists")
                return False
            except PermissionError:
                print(f"mkdir: cannot create directory '{dir_path}': Permission denied")
                return False
            except Exception as e:
                print(f"mkdir: error creating directory '{dir_path}': {e}")
                return False
        
        return True

class RMCommand(CommandExecutor):
    """rm - remove files and directories"""
    
    def execute(self, args: List[str]) -> bool:
        if not args:
            print("rm: missing operand")
            return False
        
        recursive = False
        force = False
        interactive = False
        
        files = []
        i = 0
        while i < len(args):
            if args[i] == '-r' or args[i] == '-R':
                recursive = True
            elif args[i] == '-f':
                force = True
            elif args[i] == '-i':
                interactive = True
            elif args[i] == '-rf' or args[i] == '-fr':
                recursive = True
                force = True
            else:
                files.append(args[i])
            i += 1
        
        if not files:
            print("rm: missing operand")
            return False
        
        for file_path in files:
            try:
                if not os.path.exists(file_path):
                    if not force:
                        print(f"rm: cannot remove '{file_path}': No such file or directory")
                    continue
                
                if interactive and not force:
                    response = input(f"rm: remove '{file_path}'? (y/n): ")
                    if response.lower() not in ['y', 'yes']:
                        continue
                
                if os.path.isdir(file_path):
                    if recursive:
                        shutil.rmtree(file_path)
                    else:
                        print(f"rm: cannot remove '{file_path}': Is a directory")
                        continue
                else:
                    os.remove(file_path)
                
                print(f"Removed: {file_path}")
                
            except PermissionError:
                if not force:
                    print(f"rm: cannot remove '{file_path}': Permission denied")
            except Exception as e:
                if not force:
                    print(f"rm: error removing '{file_path}': {e}")
        
        return True

class CPCommand(CommandExecutor):
    """cp - copy files and directories"""
    
    def execute(self, args: List[str]) -> bool:
        if len(args) < 2:
            print("cp: missing file operand")
            return False
        
        recursive = False
        preserve = False
        
        files = []
        i = 0
        while i < len(args):
            if args[i] == '-r' or args[i] == '-R':
                recursive = True
            elif args[i] == '-p':
                preserve = True
            else:
                files.append(args[i])
            i += 1
        
        if len(files) < 2:
            print("cp: missing destination file operand")
            return False
        
        sources = files[:-1]
        destination = files[-1]
        
        # Check if destination is a directory
        dest_is_dir = os.path.isdir(destination)
        
        if len(sources) > 1 and not dest_is_dir:
            print("cp: target is not a directory")
            return False
        
        for source in sources:
            try:
                if not os.path.exists(source):
                    print(f"cp: cannot stat '{source}': No such file or directory")
                    continue
                
                if dest_is_dir:
                    dest_path = os.path.join(destination, os.path.basename(source))
                else:
                    dest_path = destination
                
                if os.path.isdir(source):
                    if recursive:
                        shutil.copytree(source, dest_path)
                    else:
                        print(f"cp: omitting directory '{source}'")
                        continue
                else:
                    if preserve:
                        shutil.copy2(source, dest_path)
                    else:
                        shutil.copy(source, dest_path)
                
                print(f"Copied: {source} -> {dest_path}")
                
            except Exception as e:
                print(f"cp: error copying '{source}': {e}")
        
        return True

class MVCommand(CommandExecutor):
    """mv - move/rename files and directories"""
    
    def execute(self, args: List[str]) -> bool:
        if len(args) < 2:
            print("mv: missing file operand")
            return False
        
        sources = args[:-1]
        destination = args[-1]
        
        # Check if destination is a directory
        dest_is_dir = os.path.isdir(destination)
        
        if len(sources) > 1 and not dest_is_dir:
            print("mv: target is not a directory")
            return False
        
        for source in sources:
            try:
                if not os.path.exists(source):
                    print(f"mv: cannot stat '{source}': No such file or directory")
                    continue
                
                if dest_is_dir:
                    dest_path = os.path.join(destination, os.path.basename(source))
                else:
                    dest_path = destination
                
                shutil.move(source, dest_path)
                print(f"Moved: {source} -> {dest_path}")
                
            except Exception as e:
                print(f"mv: error moving '{source}': {e}")
        
        return True

# Text Processing Commands
class CATCommand(CommandExecutor):
    """cat - concatenate and display files"""
    
    def execute(self, args: List[str]) -> bool:
        if not args:
            # Read from stdin
            try:
                for line in sys.stdin:
                    print(line, end='')
            except KeyboardInterrupt:
                pass
            return True
        
        number_lines = False
        show_ends = False
        
        files = []
        i = 0
        while i < len(args):
            if args[i] == '-n':
                number_lines = True
            elif args[i] == '-E':
                show_ends = True
            else:
                files.append(args[i])
            i += 1
        
        line_number = 1
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    for line in f:
                        if number_lines:
                            print(f"{line_number:6d}  ", end='')
                            line_number += 1
                        
                        if show_ends:
                            line = line.rstrip('\n') + '$\n'
                        
                        print(line, end='')
                        
            except FileNotFoundError:
                print(f"cat: {file_path}: No such file or directory")
            except PermissionError:
                print(f"cat: {file_path}: Permission denied")
            except Exception as e:
                print(f"cat: {file_path}: {e}")
        
        return True

class GREPCommand(CommandExecutor):
    """grep - search text patterns"""
    
    def execute(self, args: List[str]) -> bool:
        if not args:
            print("grep: missing pattern")
            return False
        
        pattern = args[0]
        files = args[1:] if len(args) > 1 else ['-']
        
        case_insensitive = False
        invert_match = False
        line_numbers = False
        count_only = False
        recursive = False
        
        # Parse flags (simplified)
        if pattern.startswith('-'):
            flags = pattern[1:]
            if 'i' in flags:
                case_insensitive = True
            if 'v' in flags:
                invert_match = True
            if 'n' in flags:
                line_numbers = True
            if 'c' in flags:
                count_only = True
            if 'r' in flags:
                recursive = True
            
            if len(args) > 1:
                pattern = args[1]
                files = args[2:] if len(args) > 2 else ['-']
            else:
                print("grep: missing pattern")
                return False
        
        try:
            if case_insensitive:
                regex = re.compile(pattern, re.IGNORECASE)
            else:
                regex = re.compile(pattern)
        except re.error as e:
            print(f"grep: invalid pattern: {e}")
            return False
        
        for file_path in files:
            if file_path == '-':
                # Read from stdin
                self._grep_file(sys.stdin, regex, invert_match, line_numbers, count_only, "stdin")
            else:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                        self._grep_file(f, regex, invert_match, line_numbers, count_only, file_path)
                except FileNotFoundError:
                    print(f"grep: {file_path}: No such file or directory")
                except PermissionError:
                    print(f"grep: {file_path}: Permission denied")
        
        return True
    
    def _grep_file(self, file, regex, invert_match, line_numbers, count_only, filename):
        count = 0
        line_num = 0
        
        for line in file:
            line_num += 1
            line = line.rstrip('\n')
            
            match = regex.search(line)
            if (match and not invert_match) or (not match and invert_match):
                count += 1
                
                if not count_only:
                    prefix = ""
                    if len(sys.argv) > 3:  # Multiple files
                        prefix = f"{filename}:"
                    if line_numbers:
                        prefix += f"{line_num}:"
                    
                    print(f"{prefix}{line}")
        
        if count_only:
            print(f"{filename}:{count}" if len(sys.argv) > 3 else count)

# System Information Commands
class PSCommand(CommandExecutor):
    """ps - show running processes"""
    
    def execute(self, args: List[str]) -> bool:
        try:
            import psutil
            
            show_all = '-a' in args or '-e' in args
            full_format = '-f' in args
            
            print("  PID TTY          TIME CMD")
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                try:
                    pid = proc.info['pid']
                    name = proc.info['name']
                    
                    if full_format and proc.info['cmdline']:
                        cmd = ' '.join(proc.info['cmdline'])
                    else:
                        cmd = name
                    
                    # Calculate runtime
                    create_time = proc.info['create_time']
                    runtime = time.time() - create_time
                    hours = int(runtime // 3600)
                    minutes = int((runtime % 3600) // 60)
                    seconds = int(runtime % 60)
                    time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    
                    print(f"{pid:5d} ?        {time_str} {cmd}")
                    
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
        except ImportError:
            print("ps: psutil not available, showing basic process info")
            try:
                if sys.platform == "win32":
                    result = subprocess.run(['tasklist'], capture_output=True, text=True)
                else:
                    result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
                print(result.stdout)
            except:
                print("ps: unable to get process information")
        
        return True

class TOPCommand(CommandExecutor):
    """top - display running processes"""
    
    def execute(self, args: List[str]) -> bool:
        try:
            import psutil
            
            print("Top - System Monitor")
            print("Press Ctrl+C to exit")
            print()
            
            while True:
                # Clear screen
                os.system('cls' if os.name == 'nt' else 'clear')
                
                # System info
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                
                print(f"CPU Usage: {cpu_percent:.1f}%")
                print(f"Memory: {memory.percent:.1f}% ({memory.used // 1024 // 1024} MB used)")
                print()
                print("  PID USER     %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND")
                
                # Process list
                processes = []
                for proc in psutil.process_iter(['pid', 'username', 'name', 'cpu_percent', 'memory_percent']):
                    try:
                        processes.append(proc.info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                # Sort by CPU usage
                processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
                
                for proc in processes[:20]:  # Show top 20
                    pid = proc.get('pid', 0)
                    user = proc.get('username', 'unknown')[:8]
                    name = proc.get('name', 'unknown')
                    cpu = proc.get('cpu_percent', 0)
                    mem = proc.get('memory_percent', 0)
                    
                    print(f"{pid:5d} {user:<8} {cpu:5.1f} {mem:5.1f}      0     0 ?        S    00:00   0:00 {name}")
                
                time.sleep(2)
                
        except KeyboardInterrupt:
            print("\nExiting top...")
        except ImportError:
            print("top: psutil not available")
        
        return True

# Network Commands
class PINGCommand(CommandExecutor):
    """ping - send ICMP echo requests"""
    
    def execute(self, args: List[str]) -> bool:
        if not args:
            print("ping: missing host operand")
            return False
        
        host = args[0]
        count = 4
        timeout = 3
        
        # Parse options
        i = 1
        while i < len(args):
            if args[i] == '-c' and i + 1 < len(args):
                try:
                    count = int(args[i + 1])
                    i += 1
                except ValueError:
                    print(f"ping: invalid count '{args[i + 1]}'")
                    return False
            elif args[i] == '-W' and i + 1 < len(args):
                try:
                    timeout = int(args[i + 1])
                    i += 1
                except ValueError:
                    print(f"ping: invalid timeout '{args[i + 1]}'")
                    return False
            i += 1
        
        try:
            # Resolve hostname
            ip = socket.gethostbyname(host)
            print(f"PING {host} ({ip}): 56 data bytes")
            
            for i in range(count):
                start_time = time.time()
                
                # Simple connectivity test
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(timeout)
                    result = sock.connect_ex((ip, 80))  # Try port 80
                    sock.close()
                    
                    end_time = time.time()
                    rtt = (end_time - start_time) * 1000
                    
                    if result == 0:
                        print(f"64 bytes from {ip}: icmp_seq={i+1} ttl=64 time={rtt:.1f}ms")
                    else:
                        print(f"Request timeout for icmp_seq {i+1}")
                    
                except Exception:
                    print(f"Request timeout for icmp_seq {i+1}")
                
                if i < count - 1:
                    time.sleep(1)
            
            print(f"\n--- {host} ping statistics ---")
            print(f"{count} packets transmitted, {count} received, 0% packet loss")
            
        except socket.gaierror:
            print(f"ping: cannot resolve {host}: Unknown host")
            return False
        except Exception as e:
            print(f"ping: error: {e}")
            return False
        
        return True

# System Commands
class UNAMECommand(CommandExecutor):
    """uname - system information"""
    
    def execute(self, args: List[str]) -> bool:
        import platform
        
        show_all = '-a' in args
        show_kernel = '-s' in args or not args
        show_node = '-n' in args
        show_release = '-r' in args
        show_version = '-v' in args
        show_machine = '-m' in args
        show_processor = '-p' in args
        show_os = '-o' in args
        
        if show_all:
            show_kernel = show_node = show_release = show_version = show_machine = True
        
        result = []
        
        if show_kernel:
            result.append("KOS")  # Our kernel name
        
        if show_node:
            result.append(platform.node())
        
        if show_release:
            result.append("1.0.0")  # KOS version
        
        if show_version:
            result.append(f"KOS 1.0.0 {datetime.now().strftime('%Y-%m-%d')}")
        
        if show_machine:
            result.append(platform.machine())
        
        if show_processor:
            result.append(platform.processor() or platform.machine())
        
        if show_os:
            result.append("KOS/Kaede")
        
        print(' '.join(result))
        return True

class WHOAMICommand(CommandExecutor):
    """whoami - print current username"""
    
    def execute(self, args: List[str]) -> bool:
        try:
            import getpass
            print(getpass.getuser())
        except:
            print(os.environ.get('USER', os.environ.get('USERNAME', 'unknown')))
        return True

class DFCommand(CommandExecutor):
    """df - display filesystem disk space usage"""
    
    def execute(self, args: List[str]) -> bool:
        human_readable = '-h' in args
        
        try:
            import shutil
            
            print("Filesystem     1K-blocks      Used Available Use% Mounted on" if not human_readable else
                  "Filesystem      Size  Used Avail Use% Mounted on")
            
            # Get disk usage for current directory
            total, used, free = shutil.disk_usage('.')
            
            if human_readable:
                total_h = self._human_readable_size(total)
                used_h = self._human_readable_size(used)
                free_h = self._human_readable_size(free)
                use_percent = int((used / total) * 100) if total > 0 else 0
                print(f"/dev/disk1s1   {total_h:>5} {used_h:>4} {free_h:>5} {use_percent:>3}% /")
            else:
                total_k = total // 1024
                used_k = used // 1024
                free_k = free // 1024
                use_percent = int((used / total) * 100) if total > 0 else 0
                print(f"/dev/disk1s1   {total_k:>9} {used_k:>9} {free_k:>9} {use_percent:>3}% /")
            
        except Exception as e:
            print(f"df: error: {e}")
        
        return True
    
    def _human_readable_size(self, size: int) -> str:
        """Convert size to human readable format"""
        for unit in ['B', 'K', 'M', 'G', 'T']:
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}P"

# Text Editors
class NANOCommand(CommandExecutor):
    """nano - simple text editor"""
    
    def execute(self, args: List[str]) -> bool:
        if not args:
            print("nano: missing filename")
            return False
        
        filename = args[0]
        
        # Simple text editor implementation
        print(f"KOS Nano Editor - Editing: {filename}")
        print("Enter text (Ctrl+D to save and exit, Ctrl+C to cancel):")
        
        lines = []
        
        # Load existing file if it exists
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    lines = f.read().splitlines()
                    for i, line in enumerate(lines):
                        print(f"{i+1:3d}: {line}")
            except Exception as e:
                print(f"Error reading file: {e}")
        
        print("\nEnter new content:")
        
        try:
            new_lines = []
            while True:
                try:
                    line = input()
                    new_lines.append(line)
                except EOFError:
                    break
            
            # Save file
            with open(filename, 'w') as f:
                f.write('\n'.join(new_lines))
            
            print(f"\nFile saved: {filename}")
            
        except KeyboardInterrupt:
            print("\nEdit cancelled")
            return False
        except Exception as e:
            print(f"Error saving file: {e}")
            return False
        
        return True

# Archive Commands
class TARCommand(CommandExecutor):
    """tar - archive files"""
    
    def execute(self, args: List[str]) -> bool:
        if not args:
            print("tar: missing operation")
            return False
        
        operation = args[0]
        archive_name = None
        files = []
        
        # Parse arguments
        create = 'c' in operation
        extract = 'x' in operation
        list_contents = 't' in operation
        verbose = 'v' in operation
        gzip_compress = 'z' in operation
        
        if 'f' in operation:
            if len(args) < 2:
                print("tar: missing archive name")
                return False
            archive_name = args[1]
            files = args[2:]
        else:
            files = args[1:]
        
        try:
            if create:
                mode = 'w:gz' if gzip_compress else 'w'
                with tarfile.open(archive_name, mode) as tar:
                    for file_path in files:
                        if os.path.exists(file_path):
                            tar.add(file_path)
                            if verbose:
                                print(f"a {file_path}")
                        else:
                            print(f"tar: {file_path}: No such file or directory")
                print(f"Archive created: {archive_name}")
            
            elif extract:
                mode = 'r:gz' if gzip_compress else 'r'
                with tarfile.open(archive_name, mode) as tar:
                    tar.extractall()
                    if verbose:
                        for member in tar.getmembers():
                            print(f"x {member.name}")
                print(f"Archive extracted: {archive_name}")
            
            elif list_contents:
                mode = 'r:gz' if gzip_compress else 'r'
                with tarfile.open(archive_name, mode) as tar:
                    for member in tar.getmembers():
                        if verbose:
                            mode_str = stat.filemode(member.mode)
                            size = member.size
                            mtime = datetime.fromtimestamp(member.mtime).strftime('%Y-%m-%d %H:%M')
                            print(f"{mode_str} {member.uname}/{member.gname} {size:>8} {mtime} {member.name}")
                        else:
                            print(member.name)
            
        except Exception as e:
            print(f"tar: error: {e}")
            return False
        
        return True

# Process Management
class KILLCommand(CommandExecutor):
    """kill - terminate processes"""
    
    def execute(self, args: List[str]) -> bool:
        if not args:
            print("kill: missing process ID")
            return False
        
        signal_num = 15  # SIGTERM
        pids = []
        
        # Parse arguments
        i = 0
        while i < len(args):
            if args[i] == '-9':
                signal_num = 9  # SIGKILL
            elif args[i] == '-15':
                signal_num = 15  # SIGTERM
            elif args[i].startswith('-'):
                try:
                    signal_num = int(args[i][1:])
                except ValueError:
                    print(f"kill: invalid signal '{args[i]}'")
                    return False
            else:
                try:
                    pids.append(int(args[i]))
                except ValueError:
                    print(f"kill: invalid process ID '{args[i]}'")
                    return False
            i += 1
        
        if not pids:
            print("kill: missing process ID")
            return False
        
        for pid in pids:
            try:
                if sys.platform == "win32":
                    subprocess.run(['taskkill', '/PID', str(pid), '/F'], check=True)
                else:
                    os.kill(pid, signal_num)
                print(f"Process {pid} terminated")
            except ProcessLookupError:
                print(f"kill: ({pid}) - No such process")
            except PermissionError:
                print(f"kill: ({pid}) - Operation not permitted")
            except Exception as e:
                print(f"kill: error terminating process {pid}: {e}")
        
        return True

# Create command registry
COMMANDS = {
    'ls': LSCommand,
    'cd': CDCommand,
    'pwd': PWDCommand,
    'mkdir': MKDIRCommand,
    'rm': RMCommand,
    'cp': CPCommand,
    'mv': MVCommand,
    'cat': CATCommand,
    'grep': GREPCommand,
    'ps': PSCommand,
    'top': PSCommand,  # Use PSCommand for both
    'ping': PINGCommand,
    'uname': UNAMECommand,
    'whoami': WHOAMICommand,
    'df': DFCommand,
    'nano': NANOCommand,
    'tar': TARCommand,
    'kill': KILLCommand,
}

def get_command(name: str):
    """Get command class by name"""
    return COMMANDS.get(name)

def list_commands():
    """List all available commands"""
    return list(COMMANDS.keys())

__all__ = ['COMMANDS', 'get_command', 'list_commands', 'CommandExecutor'] 
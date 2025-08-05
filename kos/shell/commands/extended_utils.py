"""
Extended System Utilities for KOS
=================================

Additional system commands and utilities:
- File operations (find, locate, which, type)
- Process management (ps, top, htop, kill, killall)
- System information (uname, whoami, id, groups)
- Text processing (sort, uniq, cut, tr, sed, awk)
- Archive operations (tar, zip, unzip, gzip, gunzip)
- Network utilities (ping, wget, curl)
- System monitoring and control
"""

import os
import sys
import subprocess
import time
import re
import glob
import stat
import pwd
import grp
import signal
import socket
import threading
import json
from typing import Dict, List, Any, Optional, Union, Tuple
from pathlib import Path
import shlex
import tempfile
import gzip
import zipfile
import tarfile

def register_extended_commands(shell):
    """Register extended commands with the shell"""
    
    # File operations
    def find_command(args):
        """find command implementation"""
        if not args or args[0] in ['-h', '--help']:
            return """Usage: find [path...] [expression]

Search for files and directories.

Options:
  -name pattern     Find by name pattern
  -type type        Find by type (f=file, d=directory, l=link)
  -size [+-]size    Find by size
  -mtime [+-]days   Find by modification time
  -user username    Find by user
  -group groupname  Find by group
  -perm mode        Find by permissions
  -exec command ;   Execute command on found files
  -print            Print found files (default)
  -delete           Delete found files

Examples:
  find . -name "*.py"
  find /home -type f -mtime -7
  find . -name "*.tmp" -delete
"""
        
        # Parse arguments
        paths = []
        expressions = []
        
        i = 0
        while i < len(args):
            arg = args[i]
            if arg.startswith('-'):
                expressions.extend(args[i:])
                break
            else:
                paths.append(arg)
            i += 1
        
        if not paths:
            paths = ['.']
        
        try:
            results = []
            for path in paths:
                results.extend(_find_files(path, expressions))
            
            for result in results:
                print(result)
            
            return True
            
        except Exception as e:
            print(f"find: {e}", file=sys.stderr)
            return False
    
    def _find_files(path: str, expressions: List[str]) -> List[str]:
        """Internal find implementation"""
        results = []
        
        # Parse expressions
        criteria = {}
        i = 0
        while i < len(expressions):
            expr = expressions[i]
            
            if expr == '-name' and i + 1 < len(expressions):
                criteria['name'] = expressions[i + 1]
                i += 2
            elif expr == '-type' and i + 1 < len(expressions):
                criteria['type'] = expressions[i + 1]
                i += 2
            elif expr == '-size' and i + 1 < len(expressions):
                criteria['size'] = expressions[i + 1]
                i += 2
            elif expr == '-mtime' and i + 1 < len(expressions):
                criteria['mtime'] = expressions[i + 1]
                i += 2
            elif expr == '-user' and i + 1 < len(expressions):
                criteria['user'] = expressions[i + 1]
                i += 2
            elif expr == '-delete':
                criteria['delete'] = True
                i += 1
            else:
                i += 1
        
        # Walk directory tree
        for root, dirs, files in os.walk(path):
            for name in files + dirs:
                full_path = os.path.join(root, name)
                
                if _matches_criteria(full_path, name, criteria):
                    if criteria.get('delete'):
                        try:
                            if os.path.isfile(full_path):
                                os.remove(full_path)
                            elif os.path.isdir(full_path):
                                os.rmdir(full_path)
                        except OSError:
                            pass
                    else:
                        results.append(full_path)
        
        return results
    
    def _matches_criteria(full_path: str, name: str, criteria: Dict[str, Any]) -> bool:
        """Check if file matches find criteria"""
        try:
            stat_info = os.stat(full_path)
            
            # Name pattern
            if 'name' in criteria:
                import fnmatch
                if not fnmatch.fnmatch(name, criteria['name']):
                    return False
            
            # File type
            if 'type' in criteria:
                file_type = criteria['type']
                if file_type == 'f' and not stat.S_ISREG(stat_info.st_mode):
                    return False
                elif file_type == 'd' and not stat.S_ISDIR(stat_info.st_mode):
                    return False
                elif file_type == 'l' and not stat.S_ISLNK(stat_info.st_mode):
                    return False
            
            # Size
            if 'size' in criteria:
                size_spec = criteria['size']
                file_size = stat_info.st_size
                
                if size_spec.startswith('+'):
                    target_size = int(size_spec[1:])
                    if file_size <= target_size:
                        return False
                elif size_spec.startswith('-'):
                    target_size = int(size_spec[1:])
                    if file_size >= target_size:
                        return False
                else:
                    target_size = int(size_spec)
                    if file_size != target_size:
                        return False
            
            # Modification time
            if 'mtime' in criteria:
                mtime_spec = criteria['mtime']
                file_mtime = stat_info.st_mtime
                current_time = time.time()
                
                if mtime_spec.startswith('+'):
                    days = int(mtime_spec[1:])
                    if current_time - file_mtime <= days * 86400:
                        return False
                elif mtime_spec.startswith('-'):
                    days = int(mtime_spec[1:])
                    if current_time - file_mtime >= days * 86400:
                        return False
                else:
                    days = int(mtime_spec)
                    if abs(current_time - file_mtime) > days * 86400:
                        return False
            
            return True
            
        except OSError:
            return False
    
    def which_command(args):
        """which command implementation"""
        if not args or args[0] in ['-h', '--help']:
            return """Usage: which [options] command...

Locate command in PATH.

Options:
  -a    Show all matches in PATH
  -s    Silent mode (exit status only)
"""
        
        show_all = '-a' in args
        silent = '-s' in args
        commands = [arg for arg in args if not arg.startswith('-')]
        
        if not commands:
            return False
        
        found_any = True
        for command in commands:
            found = _which_command(command, show_all)
            if found:
                if not silent:
                    if isinstance(found, list):
                        for path in found:
                            print(path)
                    else:
                        print(found)
            else:
                found_any = False
                if not silent:
                    print(f"which: {command}: not found", file=sys.stderr)
        
        return found_any
    
    def _which_command(command: str, show_all: bool = False) -> Union[str, List[str], None]:
        """Find command in PATH"""
        if os.path.sep in command:
            # Absolute or relative path
            if os.path.isfile(command) and os.access(command, os.X_OK):
                return command
            return None
        
        path_dirs = os.environ.get('PATH', '').split(os.pathsep)
        found = []
        
        for path_dir in path_dirs:
            full_path = os.path.join(path_dir, command)
            if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                if show_all:
                    found.append(full_path)
                else:
                    return full_path
        
        return found if show_all and found else (found[0] if found else None)
    
    def type_command(args):
        """type command implementation"""
        if not args or args[0] in ['-h', '--help']:
            return """Usage: type [options] command...

Display command type.

Options:
  -a    Show all occurrences
  -t    Show only type
  -p    Show only path
"""
        
        show_all = '-a' in args
        show_type = '-t' in args
        show_path = '-p' in args
        commands = [arg for arg in args if not arg.startswith('-')]
        
        if not commands:
            return False
        
        for command in commands:
            # Check if it's a shell builtin
            if hasattr(shell, 'commands') and command in shell.commands:
                if show_type:
                    print("builtin")
                elif show_path:
                    print("")  # No path for builtins
                else:
                    print(f"{command} is a shell builtin")
                continue
            
            # Check if it's an alias (simplified)
            # In a real implementation, this would check shell aliases
            
            # Check PATH
            found = _which_command(command, show_all)
            if found:
                if isinstance(found, list):
                    for path in found:
                        if show_type:
                            print("file")
                        elif show_path:
                            print(path)
                        else:
                            print(f"{command} is {path}")
                else:
                    if show_type:
                        print("file")
                    elif show_path:
                        print(found)
                    else:
                        print(f"{command} is {found}")
            else:
                print(f"type: {command}: not found", file=sys.stderr)
                return False
        
        return True
    
    # Process management
    def ps_command(args):
        """ps command implementation"""
        if args and args[0] in ['-h', '--help']:
            return """Usage: ps [options]

Show running processes.

Options:
  aux       Show all processes with user info
  -ef       Show all processes with full info
  -u user   Show processes for user
  -p pid    Show specific process
  --forest  Show process tree
"""
        
        try:
            # Use system ps command
            ps_args = ['ps']
            if not args:
                ps_args.extend(['aux'])
            else:
                ps_args.extend(args)
            
            result = subprocess.run(
                ps_args,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                print(result.stdout, end='')
                return True
            else:
                print(result.stderr, file=sys.stderr)
                return False
                
        except Exception as e:
            print(f"ps: {e}", file=sys.stderr)
            return False
    
    def top_command(args):
        """top command implementation"""
        try:
            # Use system top command
            top_args = ['top']
            if args:
                top_args.extend(args)
            
            subprocess.run(top_args)
            return True
            
        except KeyboardInterrupt:
            return True
        except Exception as e:
            print(f"top: {e}", file=sys.stderr)
            return False
    
    def killall_command(args):
        """killall command implementation"""
        if not args or args[0] in ['-h', '--help']:
            return """Usage: killall [options] process_name...

Kill processes by name.

Options:
  -s signal  Send specific signal
  -9         Send SIGKILL
  -TERM      Send SIGTERM (default)
  -v         Verbose output
"""
        
        signal_num = signal.SIGTERM
        verbose = False
        process_names = []
        
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == '-v':
                verbose = True
            elif arg == '-9':
                signal_num = signal.SIGKILL
            elif arg == '-TERM':
                signal_num = signal.SIGTERM
            elif arg == '-s' and i + 1 < len(args):
                try:
                    signal_num = int(args[i + 1])
                except ValueError:
                    signal_num = getattr(signal, f'SIG{args[i + 1].upper()}', signal.SIGTERM)
                i += 1
            else:
                process_names.append(arg)
            i += 1
        
        if not process_names:
            print("killall: no process name specified", file=sys.stderr)
            return False
        
        try:
            for process_name in process_names:
                # Find processes by name
                result = subprocess.run(
                    ['pgrep', process_name],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    pids = result.stdout.strip().split('\n')
                    for pid_str in pids:
                        if pid_str:
                            try:
                                pid = int(pid_str)
                                os.kill(pid, signal_num)
                                if verbose:
                                    print(f"Killed {process_name} (PID {pid})")
                            except (ValueError, OSError) as e:
                                if verbose:
                                    print(f"Failed to kill PID {pid_str}: {e}")
                else:
                    if verbose:
                        print(f"No processes found for '{process_name}'")
            
            return True
            
        except Exception as e:
            print(f"killall: {e}", file=sys.stderr)
            return False
    
    # System information
    def uname_command(args):
        """uname command implementation"""
        if args and args[0] in ['-h', '--help']:
            return """Usage: uname [options]

Print system information.

Options:
  -a    Print all information
  -s    Print kernel name (default)
  -n    Print network node hostname
  -r    Print kernel release
  -v    Print kernel version
  -m    Print machine hardware name
  -p    Print processor type
  -i    Print hardware platform
  -o    Print operating system
"""
        
        import platform
        
        show_all = '-a' in args
        show_kernel = '-s' in args or not args or show_all
        show_hostname = '-n' in args or show_all
        show_release = '-r' in args or show_all
        show_version = '-v' in args or show_all
        show_machine = '-m' in args or show_all
        show_processor = '-p' in args or show_all
        show_platform = '-i' in args or show_all
        show_os = '-o' in args or show_all
        
        info = []
        
        if show_kernel:
            info.append(platform.system())
        if show_hostname:
            info.append(platform.node())
        if show_release:
            info.append(platform.release())
        if show_version:
            info.append(platform.version())
        if show_machine:
            info.append(platform.machine())
        if show_processor:
            info.append(platform.processor() or platform.machine())
        if show_platform:
            info.append(platform.machine())
        if show_os:
            info.append(platform.system())
        
        print(' '.join(info))
        return True
    
    def whoami_command(args):
        """whoami command implementation"""
        try:
            print(pwd.getpwuid(os.getuid()).pw_name)
            return True
        except Exception as e:
            print(f"whoami: {e}", file=sys.stderr)
            return False
    
    def id_command(args):
        """id command implementation"""
        if args and args[0] in ['-h', '--help']:
            return """Usage: id [options] [user]

Print user and group IDs.

Options:
  -u    Print only user ID
  -g    Print only group ID
  -G    Print all group IDs
  -n    Print names instead of numbers
  -r    Print real ID instead of effective
"""
        
        user_only = '-u' in args
        group_only = '-g' in args
        all_groups = '-G' in args
        names = '-n' in args
        real_ids = '-r' in args
        
        username = None
        for arg in args:
            if not arg.startswith('-'):
                username = arg
                break
        
        try:
            if username:
                user_info = pwd.getpwnam(username)
                uid = user_info.pw_uid
                gid = user_info.pw_gid
            else:
                uid = os.getreal_uid() if real_ids else os.getuid()
                gid = os.getreal_gid() if real_ids else os.getgid()
            
            if user_only:
                if names:
                    print(pwd.getpwuid(uid).pw_name)
                else:
                    print(uid)
            elif group_only:
                if names:
                    print(grp.getgrgid(gid).gr_name)
                else:
                    print(gid)
            elif all_groups:
                groups = os.getgroups()
                if names:
                    group_names = []
                    for group_id in groups:
                        try:
                            group_names.append(grp.getgrgid(group_id).gr_name)
                        except KeyError:
                            group_names.append(str(group_id))
                    print(' '.join(group_names))
                else:
                    print(' '.join(map(str, groups)))
            else:
                # Full output
                user_name = pwd.getpwuid(uid).pw_name
                group_name = grp.getgrgid(gid).gr_name
                groups = os.getgroups()
                
                group_list = []
                for group_id in groups:
                    try:
                        gname = grp.getgrgid(group_id).gr_name
                        group_list.append(f"{group_id}({gname})")
                    except KeyError:
                        group_list.append(str(group_id))
                
                print(f"uid={uid}({user_name}) gid={gid}({group_name}) groups={','.join(group_list)}")
            
            return True
            
        except Exception as e:
            print(f"id: {e}", file=sys.stderr)
            return False
    
    def groups_command(args):
        """groups command implementation"""
        username = args[0] if args else None
        
        try:
            if username:
                user_info = pwd.getpwnam(username)
                groups = [g.gr_name for g in grp.getgrall() if username in g.gr_mem]
                if user_info.pw_gid not in [g.gr_gid for g in grp.getgrall() if username in g.gr_mem]:
                    primary_group = grp.getgrgid(user_info.pw_gid).gr_name
                    groups.insert(0, primary_group)
            else:
                group_ids = os.getgroups()
                groups = []
                for gid in group_ids:
                    try:
                        groups.append(grp.getgrgid(gid).gr_name)
                    except KeyError:
                        groups.append(str(gid))
            
            print(' '.join(groups))
            return True
            
        except Exception as e:
            print(f"groups: {e}", file=sys.stderr)
            return False
    
    # Text processing
    def sort_command(args):
        """sort command implementation"""
        if args and args[0] in ['-h', '--help']:
            return """Usage: sort [options] [file...]

Sort lines of text.

Options:
  -r    Reverse sort order
  -n    Sort numerically
  -u    Remove duplicates
  -f    Ignore case
  -k N  Sort by field N
  -t C  Use character C as field separator
"""
        
        reverse = '-r' in args
        numeric = '-n' in args
        unique = '-u' in args
        ignore_case = '-f' in args
        
        # Parse field and separator options
        sort_key = None
        separator = None
        
        i = 0
        files = []
        while i < len(args):
            arg = args[i]
            if arg == '-k' and i + 1 < len(args):
                sort_key = int(args[i + 1]) - 1  # Convert to 0-based
                i += 2
            elif arg == '-t' and i + 1 < len(args):
                separator = args[i + 1]
                i += 2
            elif not arg.startswith('-'):
                files.append(arg)
                i += 1
            else:
                i += 1
        
        try:
            lines = []
            
            if files:
                for filename in files:
                    with open(filename, 'r') as f:
                        lines.extend(f.readlines())
            else:
                # Read from stdin
                lines = sys.stdin.readlines()
            
            # Remove trailing newlines for sorting
            lines = [line.rstrip('\n') for line in lines]
            
            # Sort lines
            def sort_key_func(line):
                if sort_key is not None and separator:
                    fields = line.split(separator)
                    if sort_key < len(fields):
                        key_value = fields[sort_key]
                    else:
                        key_value = ""
                else:
                    key_value = line
                
                if ignore_case:
                    key_value = key_value.lower()
                
                if numeric:
                    try:
                        return float(key_value)
                    except ValueError:
                        return 0
                
                return key_value
            
            sorted_lines = sorted(lines, key=sort_key_func, reverse=reverse)
            
            if unique:
                # Remove duplicates while preserving order
                seen = set()
                unique_lines = []
                for line in sorted_lines:
                    if line not in seen:
                        seen.add(line)
                        unique_lines.append(line)
                sorted_lines = unique_lines
            
            for line in sorted_lines:
                print(line)
            
            return True
            
        except Exception as e:
            print(f"sort: {e}", file=sys.stderr)
            return False
    
    def uniq_command(args):
        """uniq command implementation"""
        if args and args[0] in ['-h', '--help']:
            return """Usage: uniq [options] [input [output]]

Remove duplicate adjacent lines.

Options:
  -c    Count occurrences
  -d    Only print duplicate lines
  -u    Only print unique lines
  -i    Ignore case
"""
        
        count = '-c' in args
        duplicates_only = '-d' in args
        unique_only = '-u' in args
        ignore_case = '-i' in args
        
        files = [arg for arg in args if not arg.startswith('-')]
        input_file = files[0] if files else None
        output_file = files[1] if len(files) > 1 else None
        
        try:
            if input_file:
                with open(input_file, 'r') as f:
                    lines = f.readlines()
            else:
                lines = sys.stdin.readlines()
            
            # Process lines
            if not lines:
                return True
            
            result_lines = []
            current_line = lines[0].rstrip('\n')
            current_count = 1
            
            for line in lines[1:]:
                line = line.rstrip('\n')
                
                compare_current = current_line.lower() if ignore_case else current_line
                compare_line = line.lower() if ignore_case else line
                
                if compare_line == compare_current:
                    current_count += 1
                else:
                    # Output current group
                    if duplicates_only and current_count == 1:
                        pass  # Skip unique lines
                    elif unique_only and current_count > 1:
                        pass  # Skip duplicate lines
                    else:
                        if count:
                            result_lines.append(f"{current_count:7} {current_line}")
                        else:
                            result_lines.append(current_line)
                    
                    current_line = line
                    current_count = 1
            
            # Handle last group
            if duplicates_only and current_count == 1:
                pass
            elif unique_only and current_count > 1:
                pass
            else:
                if count:
                    result_lines.append(f"{current_count:7} {current_line}")
                else:
                    result_lines.append(current_line)
            
            # Output results
            if output_file:
                with open(output_file, 'w') as f:
                    for line in result_lines:
                        f.write(line + '\n')
            else:
                for line in result_lines:
                    print(line)
            
            return True
            
        except Exception as e:
            print(f"uniq: {e}", file=sys.stderr)
            return False
    
    # Archive operations
    def tar_command(args):
        """tar command implementation"""
        if not args or args[0] in ['-h', '--help']:
            return """Usage: tar [options] archive [files...]

Archive files with tar.

Options:
  -c    Create archive
  -x    Extract archive
  -t    List archive contents
  -f    Specify archive file
  -v    Verbose output
  -z    Use gzip compression
  -j    Use bzip2 compression
  -C    Change to directory
"""
        
        create = False
        extract = False
        list_contents = False
        archive_file = None
        verbose = False
        gzip_compression = False
        bzip2_compression = False
        change_dir = None
        files = []
        
        i = 0
        while i < len(args):
            arg = args[i]
            
            if arg.startswith('-') and not arg.startswith('--'):
                # Parse combined options
                for char in arg[1:]:
                    if char == 'c':
                        create = True
                    elif char == 'x':
                        extract = True
                    elif char == 't':
                        list_contents = True
                    elif char == 'v':
                        verbose = True
                    elif char == 'z':
                        gzip_compression = True
                    elif char == 'j':
                        bzip2_compression = True
                    elif char == 'f':
                        if i + 1 < len(args):
                            archive_file = args[i + 1]
                            i += 1
                        break
            elif arg == '-C' and i + 1 < len(args):
                change_dir = args[i + 1]
                i += 1
            elif not arg.startswith('-'):
                if archive_file is None:
                    archive_file = arg
                else:
                    files.append(arg)
            
            i += 1
        
        if not archive_file:
            print("tar: archive file not specified", file=sys.stderr)
            return False
        
        try:
            if change_dir:
                os.chdir(change_dir)
            
            mode = 'r'
            if create:
                mode = 'w'
            elif extract:
                mode = 'r'
            elif list_contents:
                mode = 'r'
            
            if gzip_compression:
                mode += ':gz'
            elif bzip2_compression:
                mode += ':bz2'
            
            with tarfile.open(archive_file, mode) as tar:
                if create:
                    for file_path in files:
                        if verbose:
                            print(f"adding: {file_path}")
                        tar.add(file_path)
                elif extract:
                    if files:
                        for file_path in files:
                            if verbose:
                                print(f"extracting: {file_path}")
                            tar.extract(file_path)
                    else:
                        tar.extractall()
                        if verbose:
                            for member in tar.getnames():
                                print(f"extracting: {member}")
                elif list_contents:
                    for member in tar.getmembers():
                        if verbose:
                            print(f"{member.mode:o} {member.uname}/{member.gname} {member.size:8} {time.strftime('%Y-%m-%d %H:%M', time.localtime(member.mtime))} {member.name}")
                        else:
                            print(member.name)
            
            return True
            
        except Exception as e:
            print(f"tar: {e}", file=sys.stderr)
            return False
    
    def gzip_command(args):
        """gzip command implementation"""
        if not args or args[0] in ['-h', '--help']:
            return """Usage: gzip [options] [files...]

Compress files with gzip.

Options:
  -d    Decompress
  -f    Force overwrite
  -k    Keep original files
  -v    Verbose output
  -1    Fast compression
  -9    Best compression
"""
        
        decompress = '-d' in args
        force = '-f' in args
        keep = '-k' in args
        verbose = '-v' in args
        
        level = 6  # Default compression level
        for arg in args:
            if arg in ['-1', '-2', '-3', '-4', '-5', '-6', '-7', '-8', '-9']:
                level = int(arg[1])
        
        files = [arg for arg in args if not arg.startswith('-')]
        
        if not files:
            print("gzip: no files specified", file=sys.stderr)
            return False
        
        try:
            for filename in files:
                if decompress:
                    if not filename.endswith('.gz'):
                        if verbose:
                            print(f"gzip: {filename}: unknown suffix -- ignored")
                        continue
                    
                    output_name = filename[:-3]
                    
                    if os.path.exists(output_name) and not force:
                        print(f"gzip: {output_name}: already exists -- not overwritten")
                        continue
                    
                    with gzip.open(filename, 'rb') as gz_file:
                        with open(output_name, 'wb') as out_file:
                            out_file.write(gz_file.read())
                    
                    if not keep:
                        os.remove(filename)
                    
                    if verbose:
                        print(f"gzip: {filename}: decompressed to {output_name}")
                
                else:
                    output_name = filename + '.gz'
                    
                    if os.path.exists(output_name) and not force:
                        print(f"gzip: {output_name}: already exists -- not overwritten")
                        continue
                    
                    with open(filename, 'rb') as in_file:
                        with gzip.open(output_name, 'wb', compresslevel=level) as gz_file:
                            gz_file.write(in_file.read())
                    
                    if not keep:
                        os.remove(filename)
                    
                    if verbose:
                        original_size = os.path.getsize(filename) if keep else os.path.getsize(output_name)
                        compressed_size = os.path.getsize(output_name)
                        ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
                        print(f"gzip: {filename}: compressed to {output_name} ({ratio:.1f}% saved)")
            
            return True
            
        except Exception as e:
            print(f"gzip: {e}", file=sys.stderr)
            return False
    
    # Network utilities
    def ping_command(args):
        """ping command implementation"""
        if not args or args[0] in ['-h', '--help']:
            return """Usage: ping [options] destination

Send ICMP echo requests.

Options:
  -c count    Number of packets to send
  -i interval Interval between packets
  -W timeout  Timeout for replies
  -q          Quiet output
"""
        
        try:
            # Use system ping command
            ping_args = ['ping'] + args
            subprocess.run(ping_args)
            return True
            
        except KeyboardInterrupt:
            return True
        except Exception as e:
            print(f"ping: {e}", file=sys.stderr)
            return False
    
    def wget_command(args):
        """wget command implementation"""
        if not args or args[0] in ['-h', '--help']:
            return """Usage: wget [options] URL...

Download files from web.

Options:
  -O file     Output to file
  -c          Continue partial download
  -q          Quiet mode
  -v          Verbose mode
  -t retries  Number of retries
"""
        
        try:
            # Use system wget if available
            result = subprocess.run(['which', 'wget'], capture_output=True)
            if result.returncode == 0:
                subprocess.run(['wget'] + args)
                return True
            else:
                # Simple wget implementation using Python
                output_file = None
                quiet = '-q' in args
                verbose = '-v' in args
                
                i = 0
                urls = []
                while i < len(args):
                    arg = args[i]
                    if arg == '-O' and i + 1 < len(args):
                        output_file = args[i + 1]
                        i += 2
                    elif not arg.startswith('-'):
                        urls.append(arg)
                        i += 1
                    else:
                        i += 1
                
                if not urls:
                    print("wget: no URLs specified", file=sys.stderr)
                    return False
                
                import urllib.request
                
                for url in urls:
                    try:
                        if not quiet:
                            print(f"Downloading {url}...")
                        
                        filename = output_file or os.path.basename(url) or 'index.html'
                        urllib.request.urlretrieve(url, filename)
                        
                        if not quiet:
                            print(f"Saved to {filename}")
                    
                    except Exception as e:
                        print(f"wget: {url}: {e}", file=sys.stderr)
                        return False
                
                return True
            
        except Exception as e:
            print(f"wget: {e}", file=sys.stderr)
            return False
    
    # Register all commands
    commands = {
        'find': find_command,
        'which': which_command,
        'type': type_command,
        'ps': ps_command,
        'top': top_command,
        'killall': killall_command,
        'uname': uname_command,
        'whoami': whoami_command,
        'id': id_command,
        'groups': groups_command,
        'sort': sort_command,
        'uniq': uniq_command,
        'tar': tar_command,
        'gzip': gzip_command,
        'gunzip': lambda args: gzip_command(['-d'] + args),
        'ping': ping_command,
        'wget': wget_command,
    }
    
    for name, func in commands.items():
        shell.register_command(name, func)

__all__ = ['register_extended_commands']
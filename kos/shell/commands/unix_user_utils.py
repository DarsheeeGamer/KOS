"""
Unix-like User and Permission Utilities for KOS Shell

This module provides Linux/Unix-like user management and permission commands for KOS.
"""

import os
import sys
import stat
import time
import logging
import pwd
import grp
import shutil
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

# Import KOS components
from kos.layer import klayer

# Set up logging
logger = logging.getLogger('KOS.shell.commands.unix_user_utils')

class UnixUserUtilities:
    """Unix-like user and permission management commands for KOS shell"""
    
    @staticmethod
    def do_chmod(fs, cwd, arg):
        """
        Change file mode bits
        
        Usage: chmod [options] MODE[,MODE]... FILE...
        
        Options:
          -c, --changes         Report only when a change is made
          -f, --silent          Suppress most error messages
          -v, --verbose         Output a diagnostic for every file processed
          -R, --recursive       Change files and directories recursively
          --reference=RFILE     Use RFILE's mode instead of specifying a MODE
        """
        args = arg.split()
        
        # Parse options
        report_changes = False
        silent = False
        verbose = False
        recursive = False
        reference_file = None
        
        # Process arguments
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                if args[i] in ['-c', '--changes']:
                    report_changes = True
                elif args[i] in ['-f', '--silent']:
                    silent = True
                elif args[i] in ['-v', '--verbose']:
                    verbose = True
                elif args[i] in ['-R', '--recursive']:
                    recursive = True
                elif args[i].startswith('--reference='):
                    reference_file = args[i].split('=')[1]
                else:
                    # Process combined options
                    for c in args[i][1:]:
                        if c == 'c':
                            report_changes = True
                        elif c == 'f':
                            silent = True
                        elif c == 'v':
                            verbose = True
                        elif c == 'R':
                            recursive = True
            else:
                break
            i += 1
        
        # Check if enough arguments
        if i >= len(args):
            return "chmod: missing operand\nTry 'chmod --help' for more information."
        
        # If reference file is specified, get mode from it
        if reference_file:
            try:
                # Resolve reference file path
                if not os.path.isabs(reference_file):
                    ref_path = os.path.join(cwd, reference_file)
                else:
                    ref_path = reference_file
                
                # Get mode from reference file
                mode = stat.S_IMODE(os.stat(ref_path).st_mode)
            except FileNotFoundError:
                return f"chmod: cannot stat '{reference_file}': No such file or directory"
            except PermissionError:
                return f"chmod: cannot stat '{reference_file}': Permission denied"
            
            # Start with the files (index i)
            mode_arg_index = i
        else:
            # Mode is specified as an argument
            try:
                mode_arg = args[i]
                i += 1
                mode_arg_index = i
                
                # Parse mode
                if mode_arg.isdigit():
                    # Octal mode
                    mode = int(mode_arg, 8)
                else:
                    # Symbolic mode (simplified implementation)
                    return "chmod: symbolic mode not fully implemented, use octal mode"
            except ValueError:
                return f"chmod: invalid mode: '{mode_arg}'"
            
            if mode_arg_index >= len(args):
                return "chmod: missing file operand\nTry 'chmod --help' for more information."
        
        # Process files
        results = []
        files = args[mode_arg_index:]
        
        for file_path in files:
            # Resolve path
            if not os.path.isabs(file_path):
                path = os.path.join(cwd, file_path)
            else:
                path = file_path
            
            try:
                # Check if file exists
                if not os.path.exists(path):
                    if not silent:
                        results.append(f"chmod: cannot access '{file_path}': No such file or directory")
                    continue
                
                # Check if path is a directory
                if os.path.isdir(path) and recursive:
                    # Walk directory recursively
                    for root, dirs, dir_files in os.walk(path):
                        # Change mode of the directory
                        old_mode = stat.S_IMODE(os.stat(root).st_mode)
                        os.chmod(root, mode)
                        
                        if verbose or (report_changes and old_mode != mode):
                            results.append(f"mode of '{root}' changed from {old_mode:04o} to {mode:04o}")
                        
                        # Change mode of all files in the directory
                        for file in dir_files:
                            file_path = os.path.join(root, file)
                            old_mode = stat.S_IMODE(os.stat(file_path).st_mode)
                            os.chmod(file_path, mode)
                            
                            if verbose or (report_changes and old_mode != mode):
                                results.append(f"mode of '{file_path}' changed from {old_mode:04o} to {mode:04o}")
                else:
                    # Change mode of the file
                    old_mode = stat.S_IMODE(os.stat(path).st_mode)
                    os.chmod(path, mode)
                    
                    if verbose or (report_changes and old_mode != mode):
                        results.append(f"mode of '{file_path}' changed from {old_mode:04o} to {mode:04o}")
            except PermissionError:
                if not silent:
                    results.append(f"chmod: changing permissions of '{file_path}': Operation not permitted")
            except Exception as e:
                if not silent:
                    results.append(f"chmod: {file_path}: {str(e)}")
        
        if results:
            return "\n".join(results)
        return ""  # Success with no output
    
    @staticmethod
    def do_chown(fs, cwd, arg):
        """
        Change file owner and group
        
        Usage: chown [options] [OWNER][:[GROUP]] FILE...
        
        Options:
          -c, --changes         Report only when a change is made
          -f, --silent          Suppress most error messages
          -v, --verbose         Output a diagnostic for every file processed
          -R, --recursive       Change files and directories recursively
          --reference=RFILE     Use RFILE's owner and group instead of specifying values
        """
        args = arg.split()
        
        # Parse options
        report_changes = False
        silent = False
        verbose = False
        recursive = False
        reference_file = None
        
        # Process arguments
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                if args[i] in ['-c', '--changes']:
                    report_changes = True
                elif args[i] in ['-f', '--silent']:
                    silent = True
                elif args[i] in ['-v', '--verbose']:
                    verbose = True
                elif args[i] in ['-R', '--recursive']:
                    recursive = True
                elif args[i].startswith('--reference='):
                    reference_file = args[i].split('=')[1]
                else:
                    # Process combined options
                    for c in args[i][1:]:
                        if c == 'c':
                            report_changes = True
                        elif c == 'f':
                            silent = True
                        elif c == 'v':
                            verbose = True
                        elif c == 'R':
                            recursive = True
            else:
                break
            i += 1
        
        # Check if enough arguments
        if i >= len(args):
            return "chown: missing operand\nTry 'chown --help' for more information."
        
        # If reference file is specified, get owner and group from it
        if reference_file:
            try:
                # Resolve reference file path
                if not os.path.isabs(reference_file):
                    ref_path = os.path.join(cwd, reference_file)
                else:
                    ref_path = reference_file
                
                # Get owner and group from reference file
                ref_stat = os.stat(ref_path)
                owner = ref_stat.st_uid
                group = ref_stat.st_gid
            except FileNotFoundError:
                return f"chown: cannot stat '{reference_file}': No such file or directory"
            except PermissionError:
                return f"chown: cannot stat '{reference_file}': Permission denied"
            
            # Start with the files (index i)
            owner_arg_index = i
        else:
            # Owner and group are specified as an argument
            owner_group_arg = args[i]
            i += 1
            owner_arg_index = i
            
            # Parse owner and group
            if ':' in owner_group_arg:
                owner_str, group_str = owner_group_arg.split(':', 1)
                
                # Get owner ID
                if owner_str:
                    try:
                        if owner_str.isdigit():
                            owner = int(owner_str)
                        else:
                            try:
                                owner = pwd.getpwnam(owner_str).pw_uid
                            except KeyError:
                                return f"chown: invalid user: '{owner_str}'"
                    except Exception as e:
                        return f"chown: invalid user: '{owner_str}'"
                else:
                    # No owner specified, keep current
                    owner = -1
                
                # Get group ID
                if group_str:
                    try:
                        if group_str.isdigit():
                            group = int(group_str)
                        else:
                            try:
                                group = grp.getgrnam(group_str).gr_gid
                            except KeyError:
                                return f"chown: invalid group: '{group_str}'"
                    except Exception as e:
                        return f"chown: invalid group: '{group_str}'"
                else:
                    # No group specified, keep current
                    group = -1
            else:
                # Only owner specified
                try:
                    if owner_group_arg.isdigit():
                        owner = int(owner_group_arg)
                    else:
                        try:
                            owner = pwd.getpwnam(owner_group_arg).pw_uid
                        except KeyError:
                            return f"chown: invalid user: '{owner_group_arg}'"
                except Exception as e:
                    return f"chown: invalid user: '{owner_group_arg}'"
                
                # No group specified
                group = -1
            
            if owner_arg_index >= len(args):
                return "chown: missing file operand\nTry 'chown --help' for more information."
        
        # Process files
        results = []
        files = args[owner_arg_index:]
        
        for file_path in files:
            # Resolve path
            if not os.path.isabs(file_path):
                path = os.path.join(cwd, file_path)
            else:
                path = file_path
            
            try:
                # Check if file exists
                if not os.path.exists(path):
                    if not silent:
                        results.append(f"chown: cannot access '{file_path}': No such file or directory")
                    continue
                
                # Get current owner and group
                file_stat = os.stat(path)
                current_owner = file_stat.st_uid
                current_group = file_stat.st_gid
                
                # Determine new owner and group
                new_owner = owner if owner != -1 else current_owner
                new_group = group if group != -1 else current_group
                
                # Check if path is a directory
                if os.path.isdir(path) and recursive:
                    # Walk directory recursively
                    for root, dirs, dir_files in os.walk(path):
                        # Change owner of the directory
                        root_stat = os.stat(root)
                        root_owner = root_stat.st_uid
                        root_group = root_stat.st_gid
                        
                        os.chown(root, new_owner, new_group)
                        
                        if verbose or (report_changes and (root_owner != new_owner or root_group != new_group)):
                            results.append(f"changed ownership of '{root}' from {root_owner}:{root_group} to {new_owner}:{new_group}")
                        
                        # Change owner of all files in the directory
                        for file in dir_files:
                            file_path = os.path.join(root, file)
                            file_stat = os.stat(file_path)
                            file_owner = file_stat.st_uid
                            file_group = file_stat.st_gid
                            
                            os.chown(file_path, new_owner, new_group)
                            
                            if verbose or (report_changes and (file_owner != new_owner or file_group != new_group)):
                                results.append(f"changed ownership of '{file_path}' from {file_owner}:{file_group} to {new_owner}:{new_group}")
                else:
                    # Change owner of the file
                    os.chown(path, new_owner, new_group)
                    
                    if verbose or (report_changes and (current_owner != new_owner or current_group != new_group)):
                        results.append(f"changed ownership of '{file_path}' from {current_owner}:{current_group} to {new_owner}:{new_group}")
            except PermissionError:
                if not silent:
                    results.append(f"chown: changing ownership of '{file_path}': Operation not permitted")
            except Exception as e:
                if not silent:
                    results.append(f"chown: {file_path}: {str(e)}")
        
        if results:
            return "\n".join(results)
        return ""  # Success with no output
    
    @staticmethod
    def do_whoami(fs, cwd, arg):
        """
        Print effective userid
        
        Usage: whoami [options]
        
        Options:
          None
        """
        try:
            return os.getlogin()
        except Exception as e:
            return f"whoami: could not determine user: {str(e)}"
    
    @staticmethod
    def do_id(fs, cwd, arg):
        """
        Print real and effective user and group IDs
        
        Usage: id [options] [USER]
        
        Options:
          -u, --user            Print only the effective user ID
          -g, --group           Print only the effective group ID
          -G, --groups          Print all group IDs
          -n, --name            Print a name instead of a number, for -ugG
          -r, --real            Print the real ID instead of the effective ID, with -ugG
        """
        args = arg.split()
        
        # Parse options
        print_user = False
        print_group = False
        print_groups = False
        print_name = False
        print_real = False
        
        # Process arguments
        user = None
        
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                if args[i] in ['-u', '--user']:
                    print_user = True
                elif args[i] in ['-g', '--group']:
                    print_group = True
                elif args[i] in ['-G', '--groups']:
                    print_groups = True
                elif args[i] in ['-n', '--name']:
                    print_name = True
                elif args[i] in ['-r', '--real']:
                    print_real = True
                else:
                    # Process combined options
                    for c in args[i][1:]:
                        if c == 'u':
                            print_user = True
                        elif c == 'g':
                            print_group = True
                        elif c == 'G':
                            print_groups = True
                        elif c == 'n':
                            print_name = True
                        elif c == 'r':
                            print_real = True
            else:
                user = args[i]
            i += 1
        
        try:
            if user:
                # Get info for specified user
                try:
                    pw = pwd.getpwnam(user)
                    uid = pw.pw_uid
                    gid = pw.pw_gid
                    username = pw.pw_name
                except KeyError:
                    return f"id: '{user}': no such user"
            else:
                # Get info for current user
                uid = os.getuid()
                gid = os.getgid()
                username = os.getlogin()
            
            # Get group info
            try:
                groups = [g.gr_name for g in grp.getgrall() if username in g.gr_mem]
                gr = grp.getgrgid(gid)
                groups.insert(0, gr.gr_name)  # Add primary group
                group_ids = [g.gr_gid for g in grp.getgrall() if username in g.gr_mem]
                group_ids.insert(0, gid)  # Add primary group ID
            except Exception:
                groups = []
                group_ids = [gid]
            
            # Generate output
            if print_user:
                if print_name:
                    return username
                else:
                    return str(uid)
            elif print_group:
                if print_name:
                    return groups[0]
                else:
                    return str(gid)
            elif print_groups:
                if print_name:
                    return " ".join(groups)
                else:
                    return " ".join(map(str, group_ids))
            else:
                # Full output
                result = f"uid={uid}({username}) gid={gid}({groups[0]})"
                if len(groups) > 1:
                    result += f" groups={','.join([f'{gid}({group})' for gid, group in zip(group_ids, groups)])}"
                return result
        except Exception as e:
            return f"id: error getting user information: {str(e)}"

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("chmod", UnixUserUtilities.do_chmod)
    shell.register_command("chown", UnixUserUtilities.do_chown)
    shell.register_command("whoami", UnixUserUtilities.do_whoami)
    shell.register_command("id", UnixUserUtilities.do_id)

"""
Unix-like Text Processing Utilities for KOS Shell

This module provides Linux/Unix-like text processing commands for KOS.
"""

import os
import sys
import re
import logging
import tempfile
import random
import string
from typing import Dict, List, Any, Optional, Union, TextIO, BinaryIO

# Import KOS components
from kos.layer import klayer

# Set up logging
logger = logging.getLogger('KOS.shell.commands.unix_text_utils')

class UnixTextUtilities:
    """Unix-like text processing commands for KOS shell"""
    
    @staticmethod
    def do_cat(fs, cwd, arg):
        """
        Concatenate files and print on the standard output
        
        Usage: cat [options] [file...]
        
        Options:
          -n, --number           Number all output lines
          -b, --number-nonblank  Number nonempty output lines
          -s, --squeeze-blank    Suppress repeated empty output lines
          -A, --show-all         Equivalent to -vET
          -E, --show-ends        Display $ at end of each line
          -T, --show-tabs        Display TAB characters as ^I
          -v, --show-nonprinting Use ^ and M- notation, except for LFD and TAB
        """
        args = arg.split()
        
        # Parse options
        number_lines = False
        number_nonblank = False
        squeeze_blank = False
        show_ends = False
        show_tabs = False
        show_nonprinting = False
        
        # Process arguments
        files = []
        
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                if args[i] in ['-n', '--number']:
                    number_lines = True
                elif args[i] in ['-b', '--number-nonblank']:
                    number_nonblank = True
                    number_lines = False  # -b overrides -n
                elif args[i] in ['-s', '--squeeze-blank']:
                    squeeze_blank = True
                elif args[i] in ['-A', '--show-all']:
                    show_ends = True
                    show_tabs = True
                    show_nonprinting = True
                elif args[i] in ['-E', '--show-ends']:
                    show_ends = True
                elif args[i] in ['-T', '--show-tabs']:
                    show_tabs = True
                elif args[i] in ['-v', '--show-nonprinting']:
                    show_nonprinting = True
                else:
                    # Process combined options
                    for c in args[i][1:]:
                        if c == 'n':
                            number_lines = True
                        elif c == 'b':
                            number_nonblank = True
                            number_lines = False
                        elif c == 's':
                            squeeze_blank = True
                        elif c == 'A':
                            show_ends = True
                            show_tabs = True
                            show_nonprinting = True
                        elif c == 'E':
                            show_ends = True
                        elif c == 'T':
                            show_tabs = True
                        elif c == 'v':
                            show_nonprinting = True
            else:
                files.append(args[i])
            i += 1
        
        # If no files specified, read from stdin (not implemented here)
        if not files:
            return "cat: No files specified. Use 'cat file1 [file2 ...]'"
        
        results = []
        line_number = 1
        last_was_blank = False
        
        # Process each file
        for file_path in files:
            # Resolve path
            if not os.path.isabs(file_path):
                path = os.path.join(cwd, file_path)
            else:
                path = file_path
            
            try:
                # Check if file exists
                if not os.path.exists(path):
                    results.append(f"cat: {file_path}: No such file or directory")
                    continue
                
                # Check if file is a directory
                if os.path.isdir(path):
                    results.append(f"cat: {file_path}: Is a directory")
                    continue
                
                # Read file
                with open(path, 'r', errors='replace') as f:
                    for line in f:
                        # Remove trailing newline
                        line = line.rstrip('\n')
                        
                        # Handle squeeze blank lines
                        if squeeze_blank and not line:
                            if last_was_blank:
                                continue
                            last_was_blank = True
                        else:
                            last_was_blank = False
                        
                        # Process line for display
                        display_line = line
                        
                        # Show tabs
                        if show_tabs:
                            display_line = display_line.replace('\t', '^I')
                        
                        # Show non-printing characters
                        if show_nonprinting:
                            new_line = ''
                            for c in display_line:
                                if ord(c) < 32 and c != '\t':
                                    new_line += '^' + chr(ord(c) + 64)
                                elif ord(c) == 127:
                                    new_line += '^?'
                                else:
                                    new_line += c
                            display_line = new_line
                        
                        # Show line endings
                        if show_ends:
                            display_line = display_line + '$'
                        
                        # Number lines
                        if number_lines:
                            results.append(f"{line_number:6}  {display_line}")
                            line_number += 1
                        elif number_nonblank:
                            if line:
                                results.append(f"{line_number:6}  {display_line}")
                                line_number += 1
                            else:
                                results.append(display_line)
                        else:
                            results.append(display_line)
                
            except PermissionError:
                results.append(f"cat: {file_path}: Permission denied")
            except UnicodeDecodeError:
                results.append(f"cat: {file_path}: Binary file")
            except Exception as e:
                results.append(f"cat: {file_path}: {str(e)}")
        
        return "\n".join(results)
    
    @staticmethod
    def do_grep(fs, cwd, arg):
        """
        Print lines matching a pattern
        
        Usage: grep [options] PATTERN [FILE...]
        
        Options:
          -i, --ignore-case     Ignore case distinctions in patterns and data
          -v, --invert-match    Select non-matching lines
          -n, --line-number     Print line number with output lines
          -c, --count           Print only a count of matching lines per FILE
          -r, --recursive       Read all files under each directory, recursively
          -l, --files-with-matches  Print only names of FILEs with matches
          -L, --files-without-match Print only names of FILEs with no match
          -E, --extended-regexp Use extended regular expressions
        """
        args = arg.split()
        
        # Need at least a pattern
        if not args:
            return "grep: no pattern specified\nUsage: grep [options] PATTERN [FILE...]"
        
        # Parse options
        ignore_case = False
        invert_match = False
        line_number = False
        count_only = False
        recursive = False
        files_with_matches = False
        files_without_match = False
        extended_regexp = False
        
        # Process arguments and extract pattern
        pattern = None
        files = []
        
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                if args[i] in ['-i', '--ignore-case']:
                    ignore_case = True
                elif args[i] in ['-v', '--invert-match']:
                    invert_match = True
                elif args[i] in ['-n', '--line-number']:
                    line_number = True
                elif args[i] in ['-c', '--count']:
                    count_only = True
                elif args[i] in ['-r', '--recursive']:
                    recursive = True
                elif args[i] in ['-l', '--files-with-matches']:
                    files_with_matches = True
                elif args[i] in ['-L', '--files-without-match']:
                    files_without_match = True
                elif args[i] in ['-E', '--extended-regexp']:
                    extended_regexp = True
                else:
                    # Process combined options
                    for c in args[i][1:]:
                        if c == 'i':
                            ignore_case = True
                        elif c == 'v':
                            invert_match = True
                        elif c == 'n':
                            line_number = True
                        elif c == 'c':
                            count_only = True
                        elif c == 'r':
                            recursive = True
                        elif c == 'l':
                            files_with_matches = True
                        elif c == 'L':
                            files_without_match = True
                        elif c == 'E':
                            extended_regexp = True
            else:
                if pattern is None:
                    pattern = args[i]
                else:
                    files.append(args[i])
            i += 1
        
        if pattern is None:
            return "grep: no pattern specified\nUsage: grep [options] PATTERN [FILE...]"
        
        # If no files specified, read from stdin (not implemented here)
        if not files:
            return "grep: No files specified. Use 'grep PATTERN file1 [file2 ...]'"
        
        # Compile the pattern
        try:
            if ignore_case:
                if extended_regexp:
                    regex = re.compile(pattern, re.IGNORECASE)
                else:
                    regex = re.compile(re.escape(pattern), re.IGNORECASE)
            else:
                if extended_regexp:
                    regex = re.compile(pattern)
                else:
                    regex = re.compile(re.escape(pattern))
        except re.error as e:
            return f"grep: invalid pattern: {str(e)}"
        
        results = []
        file_count = 0
        
        # Process each file or directory
        for file_path in files:
            # Resolve path
            if not os.path.isabs(file_path):
                path = os.path.join(cwd, file_path)
            else:
                path = file_path
            
            # Process files
            try:
                if os.path.isdir(path):
                    if recursive:
                        # Walk directory recursively
                        for root, dirs, dir_files in os.walk(path):
                            for file in dir_files:
                                file_path = os.path.join(root, file)
                                file_count += 1
                                result = UnixTextUtilities._grep_file(
                                    file_path, regex, invert_match, line_number, 
                                    count_only, files_with_matches, files_without_match
                                )
                                if result:
                                    if file_count > 1 and not (files_with_matches or files_without_match):
                                        results.append(f"{file_path}:{result}")
                                    else:
                                        results.append(result)
                    else:
                        results.append(f"grep: {file_path}: Is a directory")
                else:
                    file_count += 1
                    result = UnixTextUtilities._grep_file(
                        path, regex, invert_match, line_number, 
                        count_only, files_with_matches, files_without_match
                    )
                    if result:
                        if file_count > 1 and not (files_with_matches or files_without_match):
                            results.append(f"{file_path}:{result}")
                        else:
                            results.append(result)
            except PermissionError:
                results.append(f"grep: {file_path}: Permission denied")
            except Exception as e:
                results.append(f"grep: {file_path}: {str(e)}")
        
        return "\n".join(results)
    
    @staticmethod
    def _grep_file(file_path, regex, invert_match, line_number, count_only, files_with_matches, files_without_match):
        """Helper function to grep a single file"""
        try:
            with open(file_path, 'r', errors='replace') as f:
                lines = f.readlines()
                
                matching_lines = []
                for i, line in enumerate(lines):
                    line = line.rstrip('\n')
                    match = regex.search(line)
                    if (match and not invert_match) or (not match and invert_match):
                        if line_number:
                            matching_lines.append(f"{i+1}:{line}")
                        else:
                            matching_lines.append(line)
                
                match_count = len(matching_lines)
                
                if files_with_matches:
                    if match_count > 0:
                        return file_path
                    return None
                elif files_without_match:
                    if match_count == 0:
                        return file_path
                    return None
                elif count_only:
                    return str(match_count)
                else:
                    return "\n".join(matching_lines)
        except UnicodeDecodeError:
            # Skip binary files
            return f"Binary file {file_path} matches" if not (files_with_matches or files_without_match) else None
    
    @staticmethod
    def do_head(fs, cwd, arg):
        """
        Output the first part of files
        
        Usage: head [options] [file...]
        
        Options:
          -n, --lines=N         Print the first N lines
          -c, --bytes=N         Print the first N bytes
          -q, --quiet           Never print headers giving file names
          -v, --verbose         Always print headers giving file names
        """
        args = arg.split()
        
        # Parse options
        num_lines = 10  # Default
        num_bytes = None
        quiet = False
        verbose = False
        
        # Process arguments
        files = []
        
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                if args[i] in ['-q', '--quiet']:
                    quiet = True
                    verbose = False
                elif args[i] in ['-v', '--verbose']:
                    verbose = True
                    quiet = False
                elif args[i].startswith('-n=') or args[i].startswith('--lines='):
                    try:
                        num_lines = int(args[i].split('=')[1])
                        num_bytes = None
                    except ValueError:
                        return f"head: invalid number of lines: '{args[i].split('=')[1]}'"
                elif args[i].startswith('-c=') or args[i].startswith('--bytes='):
                    try:
                        num_bytes = int(args[i].split('=')[1])
                        num_lines = None
                    except ValueError:
                        return f"head: invalid number of bytes: '{args[i].split('=')[1]}'"
                elif args[i].startswith('-n'):
                    try:
                        num_lines = int(args[i][2:])
                        num_bytes = None
                    except ValueError:
                        return f"head: invalid number of lines: '{args[i][2:]}'"
                elif args[i].startswith('-c'):
                    try:
                        num_bytes = int(args[i][2:])
                        num_lines = None
                    except ValueError:
                        return f"head: invalid number of bytes: '{args[i][2:]}'"
                elif args[i] == '-':
                    # Read from stdin (not implemented)
                    return "head: reading from stdin not implemented"
            else:
                files.append(args[i])
            i += 1
        
        # If no files specified, read from stdin (not implemented here)
        if not files:
            return "head: No files specified. Use 'head file1 [file2 ...]'"
        
        results = []
        
        # Process each file
        for file_path in files:
            # Resolve path
            if not os.path.isabs(file_path):
                path = os.path.join(cwd, file_path)
            else:
                path = file_path
            
            try:
                # Check if file exists
                if not os.path.exists(path):
                    results.append(f"head: {file_path}: No such file or directory")
                    continue
                
                # Check if file is a directory
                if os.path.isdir(path):
                    results.append(f"head: {file_path}: Is a directory")
                    continue
                
                # Print header if multiple files and not quiet
                if (len(files) > 1 or verbose) and not quiet:
                    results.append(f"==> {file_path} <==")
                
                # Read file
                if num_bytes is not None:
                    with open(path, 'rb') as f:
                        content = f.read(num_bytes)
                        results.append(content.decode('utf-8', errors='replace'))
                else:
                    with open(path, 'r', errors='replace') as f:
                        lines = []
                        for i, line in enumerate(f):
                            if i >= num_lines:
                                break
                            lines.append(line.rstrip('\n'))
                        results.append("\n".join(lines))
                
                # Add a blank line between files
                if len(files) > 1 and not quiet:
                    results.append("")
                
            except PermissionError:
                results.append(f"head: {file_path}: Permission denied")
            except Exception as e:
                results.append(f"head: {file_path}: {str(e)}")
        
        return "\n".join(results)
    
    @staticmethod
    def do_tail(fs, cwd, arg):
        """
        Output the last part of files
        
        Usage: tail [options] [file...]
        
        Options:
          -n, --lines=N         Print the last N lines
          -c, --bytes=N         Print the last N bytes
          -q, --quiet           Never print headers giving file names
          -v, --verbose         Always print headers giving file names
          -f, --follow          Output appended data as the file grows (not implemented)
        """
        args = arg.split()
        
        # Parse options
        num_lines = 10  # Default
        num_bytes = None
        quiet = False
        verbose = False
        follow = False
        
        # Process arguments
        files = []
        
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                if args[i] in ['-q', '--quiet']:
                    quiet = True
                    verbose = False
                elif args[i] in ['-v', '--verbose']:
                    verbose = True
                    quiet = False
                elif args[i] in ['-f', '--follow']:
                    follow = True
                elif args[i].startswith('-n=') or args[i].startswith('--lines='):
                    try:
                        num_lines = int(args[i].split('=')[1])
                        num_bytes = None
                    except ValueError:
                        return f"tail: invalid number of lines: '{args[i].split('=')[1]}'"
                elif args[i].startswith('-c=') or args[i].startswith('--bytes='):
                    try:
                        num_bytes = int(args[i].split('=')[1])
                        num_lines = None
                    except ValueError:
                        return f"tail: invalid number of bytes: '{args[i].split('=')[1]}'"
                elif args[i].startswith('-n'):
                    try:
                        num_lines = int(args[i][2:])
                        num_bytes = None
                    except ValueError:
                        return f"tail: invalid number of lines: '{args[i][2:]}'"
                elif args[i].startswith('-c'):
                    try:
                        num_bytes = int(args[i][2:])
                        num_lines = None
                    except ValueError:
                        return f"tail: invalid number of bytes: '{args[i][2:]}'"
                elif args[i] == '-':
                    # Read from stdin (not implemented)
                    return "tail: reading from stdin not implemented"
            else:
                files.append(args[i])
            i += 1
        
        # If no files specified, read from stdin (not implemented here)
        if not files:
            return "tail: No files specified. Use 'tail file1 [file2 ...]'"
        
        if follow:
            return "tail: --follow option not implemented"
        
        results = []
        
        # Process each file
        for file_path in files:
            # Resolve path
            if not os.path.isabs(file_path):
                path = os.path.join(cwd, file_path)
            else:
                path = file_path
            
            try:
                # Check if file exists
                if not os.path.exists(path):
                    results.append(f"tail: {file_path}: No such file or directory")
                    continue
                
                # Check if file is a directory
                if os.path.isdir(path):
                    results.append(f"tail: {file_path}: Is a directory")
                    continue
                
                # Print header if multiple files and not quiet
                if (len(files) > 1 or verbose) and not quiet:
                    results.append(f"==> {file_path} <==")
                
                # Read file
                if num_bytes is not None:
                    with open(path, 'rb') as f:
                        f.seek(0, 2)  # Seek to end
                        file_size = f.tell()
                        if num_bytes >= file_size:
                            f.seek(0)
                        else:
                            f.seek(-num_bytes, 2)
                        content = f.read()
                        results.append(content.decode('utf-8', errors='replace'))
                else:
                    with open(path, 'r', errors='replace') as f:
                        lines = f.readlines()
                        last_lines = lines[-num_lines:] if num_lines < len(lines) else lines
                        results.append("".join(last_lines).rstrip())
                
                # Add a blank line between files
                if len(files) > 1 and not quiet:
                    results.append("")
                
            except PermissionError:
                results.append(f"tail: {file_path}: Permission denied")
            except Exception as e:
                results.append(f"tail: {file_path}: {str(e)}")
        
        return "\n".join(results)
    
    @staticmethod
    def do_touch(fs, cwd, arg):
        """
        Change file timestamps or create empty files
        
        Usage: touch [options] file...
        
        Options:
          -a                     Change only access time
          -c, --no-create        Do not create any files
          -m                     Change only modification time
          -r, --reference=FILE   Use this file's times instead of current time
        """
        args = arg.split()
        
        # Parse options
        change_access = True
        change_modification = True
        no_create = False
        reference_file = None
        
        # Process arguments
        files = []
        
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                if args[i] == '-a':
                    change_access = True
                    change_modification = False
                elif args[i] == '-m':
                    change_access = False
                    change_modification = True
                elif args[i] in ['-c', '--no-create']:
                    no_create = True
                elif args[i].startswith('-r=') or args[i].startswith('--reference='):
                    reference_file = args[i].split('=')[1]
                elif args[i].startswith('-r'):
                    if i + 1 < len(args):
                        reference_file = args[i+1]
                        i += 1
                    else:
                        return "touch: option requires an argument -- 'r'"
                else:
                    # Process combined options
                    for c in args[i][1:]:
                        if c == 'a':
                            change_access = True
                            change_modification = False
                        elif c == 'm':
                            change_access = False
                            change_modification = True
                        elif c == 'c':
                            no_create = True
            else:
                files.append(args[i])
            i += 1
        
        if not files:
            return "touch: missing file operand\nTry 'touch --help' for more information."
        
        results = []
        
        # Get reference file times if specified
        ref_atime = None
        ref_mtime = None
        
        if reference_file:
            # Resolve reference file path
            if not os.path.isabs(reference_file):
                ref_path = os.path.join(cwd, reference_file)
            else:
                ref_path = reference_file
            
            try:
                ref_stat = os.stat(ref_path)
                ref_atime = ref_stat.st_atime
                ref_mtime = ref_stat.st_mtime
            except FileNotFoundError:
                results.append(f"touch: failed to get attributes of '{reference_file}': No such file or directory")
                return "\n".join(results)
            except PermissionError:
                results.append(f"touch: failed to get attributes of '{reference_file}': Permission denied")
                return "\n".join(results)
        
        # Process each file
        for file_path in files:
            # Resolve path
            if not os.path.isabs(file_path):
                path = os.path.join(cwd, file_path)
            else:
                path = file_path
            
            try:
                # Check if file exists
                if os.path.exists(path):
                    # Update timestamps
                    if reference_file:
                        if change_access and change_modification:
                            os.utime(path, (ref_atime, ref_mtime))
                        elif change_access:
                            current_stat = os.stat(path)
                            os.utime(path, (ref_atime, current_stat.st_mtime))
                        elif change_modification:
                            current_stat = os.stat(path)
                            os.utime(path, (current_stat.st_atime, ref_mtime))
                    else:
                        if change_access and change_modification:
                            os.utime(path, None)  # Use current time
                        else:
                            current_stat = os.stat(path)
                            current_time = time.time()
                            if change_access:
                                os.utime(path, (current_time, current_stat.st_mtime))
                            elif change_modification:
                                os.utime(path, (current_stat.st_atime, current_time))
                else:
                    # Create file if it doesn't exist and no_create is False
                    if not no_create:
                        # Create parent directories if they don't exist
                        os.makedirs(os.path.dirname(path), exist_ok=True)
                        
                        # Create empty file
                        with open(path, 'a'):
                            pass
                        
                        # Set timestamps if reference file specified
                        if reference_file:
                            os.utime(path, (ref_atime, ref_mtime))
            except PermissionError:
                results.append(f"touch: cannot touch '{file_path}': Permission denied")
            except FileNotFoundError:
                # This could happen if parent directory doesn't exist
                results.append(f"touch: cannot touch '{file_path}': No such file or directory")
            except Exception as e:
                results.append(f"touch: {file_path}: {str(e)}")
        
        if results:
            return "\n".join(results)
        return ""  # Success with no output

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("cat", UnixTextUtilities.do_cat)
    shell.register_command("grep", UnixTextUtilities.do_grep)
    shell.register_command("head", UnixTextUtilities.do_head)
    shell.register_command("tail", UnixTextUtilities.do_tail)
    shell.register_command("touch", UnixTextUtilities.do_touch)

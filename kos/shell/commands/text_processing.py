"""
Text Processing Commands for KOS shell.

This module implements various text processing utilities similar to common
Unix/Linux commands like uniq, comm, expand, fold, etc.
"""

import re
import os
import shlex
import logging
from typing import List, Dict, Optional, Any, Tuple

logger = logging.getLogger('KOS.shell.text_processing')

class TextProcessingCommands:
    """Implementation of text processing commands for the KOS shell."""
    
    @staticmethod
    def do_uniq(fs, cwd, arg):
        """Filter adjacent matching lines from input
        
        Usage: uniq [OPTION]... [INPUT [OUTPUT]]
        Filter adjacent matching lines from INPUT (or standard input),
        writing to OUTPUT (or standard output).
        
        Options:
          -c, --count           Prefix lines by the number of occurrences
          -d, --repeated        Only print duplicate lines, one for each group
          -D                    Print all duplicate lines
          -f, --skip-fields=N   Avoid comparing the first N fields
          -i, --ignore-case     Ignore differences in case when comparing
          -s, --skip-chars=N    Avoid comparing the first N characters
          -u, --unique          Only print unique lines
          -z, --zero-terminated End lines with 0 byte, not newline
        """
        try:
            args = shlex.split(arg)
            
            # Parse options
            count = False
            repeated = False
            all_repeated = False
            skip_fields = 0
            ignore_case = False
            skip_chars = 0
            unique_only = False
            zero_terminated = False
            input_file = None
            output_file = None
            
            i = 0
            while i < len(args):
                if args[i] in ['-h', '--help']:
                    return TextProcessingCommands.do_uniq.__doc__
                elif args[i] in ['-c', '--count']:
                    count = True
                elif args[i] in ['-d', '--repeated']:
                    repeated = True
                elif args[i] == '-D':
                    all_repeated = True
                elif args[i].startswith('-f=') or args[i].startswith('--skip-fields='):
                    try:
                        skip_fields = int(args[i].split('=', 1)[1])
                    except ValueError:
                        return f"uniq: invalid number of fields to skip: '{args[i].split('=', 1)[1]}'"
                elif args[i] in ['-f', '--skip-fields']:
                    if i + 1 < len(args):
                        try:
                            skip_fields = int(args[i + 1])
                            i += 1
                        except ValueError:
                            return f"uniq: invalid number of fields to skip: '{args[i + 1]}'"
                    else:
                        return "uniq: option requires an argument -- 'f'"
                elif args[i] in ['-i', '--ignore-case']:
                    ignore_case = True
                elif args[i].startswith('-s=') or args[i].startswith('--skip-chars='):
                    try:
                        skip_chars = int(args[i].split('=', 1)[1])
                    except ValueError:
                        return f"uniq: invalid number of characters to skip: '{args[i].split('=', 1)[1]}'"
                elif args[i] in ['-s', '--skip-chars']:
                    if i + 1 < len(args):
                        try:
                            skip_chars = int(args[i + 1])
                            i += 1
                        except ValueError:
                            return f"uniq: invalid number of characters to skip: '{args[i + 1]}'"
                    else:
                        return "uniq: option requires an argument -- 's'"
                elif args[i] in ['-u', '--unique']:
                    unique_only = True
                elif args[i] in ['-z', '--zero-terminated']:
                    zero_terminated = True
                elif input_file is None:
                    input_file = args[i]
                elif output_file is None:
                    output_file = args[i]
                else:
                    return f"uniq: extra operand '{args[i]}'"
                i += 1
            
            # Read input
            if input_file:
                # Resolve input path
                input_path = os.path.join(cwd, input_file) if not os.path.isabs(input_file) else input_file
                
                # Check if file exists
                if not fs.exists(input_path):
                    return f"uniq: {input_file}: No such file or directory"
                
                # Check if it's a directory
                if fs.is_dir(input_path):
                    return f"uniq: {input_file}: Is a directory"
                
                # Read content
                content = fs.read_file(input_path)
            else:
                # Use stdin in a real implementation
                # For this demo, use sample text
                content = "Line 1\nLine 2\nLine 2\nLine 3\nline 3\nLine 4\nLine 4\nLine 4\n"
            
            # Split content into lines
            delimiter = '\0' if zero_terminated else '\n'
            lines = content.split(delimiter)
            
            # Process lines
            result = []
            i = 0
            while i < len(lines):
                # Get the key for comparison
                line = lines[i]
                
                # Apply skip fields if needed
                if skip_fields > 0:
                    fields = line.split()
                    key = ' '.join(fields[min(skip_fields, len(fields)):])
                else:
                    key = line
                
                # Apply skip chars if needed
                if skip_chars > 0:
                    key = key[min(skip_chars, len(key)):]
                
                # Apply ignore case if needed
                if ignore_case:
                    key = key.lower()
                
                # Count occurrences
                occurrence = 1
                j = i + 1
                while j < len(lines):
                    # Get comparison key for next line
                    next_line = lines[j]
                    
                    if skip_fields > 0:
                        next_fields = next_line.split()
                        next_key = ' '.join(next_fields[min(skip_fields, len(next_fields)):])
                    else:
                        next_key = next_line
                    
                    if skip_chars > 0:
                        next_key = next_key[min(skip_chars, len(next_key)):]
                    
                    if ignore_case:
                        next_key = next_key.lower()
                    
                    # Compare keys
                    if key == next_key:
                        occurrence += 1
                        j += 1
                    else:
                        break
                
                # Determine if line should be output
                output_line = True
                if repeated and occurrence <= 1:
                    output_line = False
                elif all_repeated and occurrence <= 1:
                    output_line = False
                elif unique_only and occurrence > 1:
                    output_line = False
                
                # Format output
                if output_line:
                    if count:
                        prefix = f"{occurrence:7d} "
                    else:
                        prefix = ""
                    
                    if all_repeated:
                        for k in range(occurrence):
                            result.append(f"{prefix}{lines[i+k]}")
                    else:
                        result.append(f"{prefix}{lines[i]}")
                
                # Move to the next unique line
                i = j
            
            # Write output
            output = delimiter.join(result)
            
            if output_file:
                # Resolve output path
                output_path = os.path.join(cwd, output_file) if not os.path.isabs(output_file) else output_file
                
                # Write to output file
                try:
                    fs.write_file(output_path, output)
                    return f"Output written to {output_file}"
                except Exception as e:
                    return f"uniq: {output_file}: {str(e)}"
            else:
                # Print to stdout
                return output
                
        except Exception as e:
            logger.error(f"Error in uniq command: {e}")
            return f"uniq: {str(e)}"
    
    @staticmethod
    def do_comm(fs, cwd, arg):
        """Compare two sorted files line by line
        
        Usage: comm [OPTION]... FILE1 FILE2
        Compare sorted files FILE1 and FILE2 line by line.
        
        Options:
          -1              Suppress column 1 (lines unique to FILE1)
          -2              Suppress column 2 (lines unique to FILE2)
          -3              Suppress column 3 (lines that appear in both files)
          --output-delimiter=STR  Use STR as the output delimiter
          --check-order    Check that the input is correctly sorted
          --nocheck-order  Do not check that the input is correctly sorted
        """
        try:
            args = shlex.split(arg)
            
            # Parse options
            suppress_col1 = False
            suppress_col2 = False
            suppress_col3 = False
            output_delimiter = '\t'
            check_order = True
            file1 = None
            file2 = None
            
            i = 0
            while i < len(args):
                if args[i] in ['-h', '--help']:
                    return TextProcessingCommands.do_comm.__doc__
                elif args[i] == '-1':
                    suppress_col1 = True
                elif args[i] == '-2':
                    suppress_col2 = True
                elif args[i] == '-3':
                    suppress_col3 = True
                elif args[i].startswith('--output-delimiter='):
                    output_delimiter = args[i].split('=', 1)[1]
                elif args[i] == '--check-order':
                    check_order = True
                elif args[i] == '--nocheck-order':
                    check_order = False
                elif file1 is None:
                    file1 = args[i]
                elif file2 is None:
                    file2 = args[i]
                else:
                    return f"comm: extra operand '{args[i]}'"
                i += 1
            
            # Check if both files are provided
            if file1 is None or file2 is None:
                return "comm: missing operand\nTry 'comm --help' for more information."
            
            # Resolve paths
            path1 = os.path.join(cwd, file1) if not os.path.isabs(file1) else file1
            path2 = os.path.join(cwd, file2) if not os.path.isabs(file2) else file2
            
            # Check if files exist
            if not fs.exists(path1):
                return f"comm: {file1}: No such file or directory"
            if not fs.exists(path2):
                return f"comm: {file2}: No such file or directory"
            
            # Check if they are directories
            if fs.is_dir(path1):
                return f"comm: {file1}: Is a directory"
            if fs.is_dir(path2):
                return f"comm: {file2}: Is a directory"
            
            # Read content
            lines1 = fs.read_file(path1).split('\n')
            lines2 = fs.read_file(path2).split('\n')
            
            # Check if files are sorted
            if check_order:
                if sorted(lines1) != lines1:
                    return f"comm: file 1 is not in sorted order"
                if sorted(lines2) != lines2:
                    return f"comm: file 2 is not in sorted order"
            
            # Compare files
            result = []
            i = j = 0
            
            while i < len(lines1) and j < len(lines2):
                if lines1[i] < lines2[j]:
                    # Line only in file1
                    if not suppress_col1:
                        result.append(lines1[i])
                    i += 1
                elif lines1[i] > lines2[j]:
                    # Line only in file2
                    if not suppress_col2:
                        result.append(output_delimiter + lines2[j])
                    j += 1
                else:
                    # Line in both files
                    if not suppress_col3:
                        result.append(output_delimiter + output_delimiter + lines1[i])
                    i += 1
                    j += 1
            
            # Process remaining lines in file1
            while i < len(lines1):
                if not suppress_col1:
                    result.append(lines1[i])
                i += 1
            
            # Process remaining lines in file2
            while j < len(lines2):
                if not suppress_col2:
                    result.append(output_delimiter + lines2[j])
                j += 1
            
            return '\n'.join(result)
                
        except Exception as e:
            logger.error(f"Error in comm command: {e}")
            return f"comm: {str(e)}"
    
    @staticmethod
    def do_expand(fs, cwd, arg):
        """Convert tabs to spaces
        
        Usage: expand [OPTION]... [FILE]...
        Convert tabs in each FILE to spaces, writing to standard output.
        
        Options:
          -i, --initial       Do not convert tabs after non blanks
          -t, --tabs=N        Have tabs N characters apart, not 8
          -t, --tabs=LIST     Use comma separated list of tab positions
        """
        try:
            args = shlex.split(arg)
            
            # Parse options
            initial_only = False
            tab_size = 8
            tab_stops = None
            files = []
            
            i = 0
            while i < len(args):
                if args[i] in ['-h', '--help']:
                    return TextProcessingCommands.do_expand.__doc__
                elif args[i] in ['-i', '--initial']:
                    initial_only = True
                elif args[i].startswith('-t=') or args[i].startswith('--tabs='):
                    tab_spec = args[i].split('=', 1)[1]
                    if ',' in tab_spec:
                        try:
                            tab_stops = [int(x) for x in tab_spec.split(',')]
                        except ValueError:
                            return f"expand: invalid tab stop: '{tab_spec}'"
                    else:
                        try:
                            tab_size = int(tab_spec)
                        except ValueError:
                            return f"expand: invalid tab size: '{tab_spec}'"
                elif args[i] in ['-t', '--tabs']:
                    if i + 1 < len(args):
                        tab_spec = args[i + 1]
                        if ',' in tab_spec:
                            try:
                                tab_stops = [int(x) for x in tab_spec.split(',')]
                            except ValueError:
                                return f"expand: invalid tab stop: '{tab_spec}'"
                        else:
                            try:
                                tab_size = int(tab_spec)
                            except ValueError:
                                return f"expand: invalid tab size: '{tab_spec}'"
                        i += 1
                    else:
                        return "expand: option requires an argument -- 't'"
                else:
                    files.append(args[i])
                i += 1
            
            # Process files
            result = []
            
            for file in files or ['-']:
                if file == '-':
                    # Use stdin in a real implementation
                    # For this demo, use sample text
                    content = "Line with\ttabs\tin it\nAnother\tline\twith tabs"
                else:
                    # Resolve path
                    path = os.path.join(cwd, file) if not os.path.isabs(file) else file
                    
                    # Check if file exists
                    if not fs.exists(path):
                        result.append(f"expand: {file}: No such file or directory")
                        continue
                    
                    # Check if it's a directory
                    if fs.is_dir(path):
                        result.append(f"expand: {file}: Is a directory")
                        continue
                    
                    # Read content
                    content = fs.read_file(path)
                
                # Process content
                lines = content.split('\n')
                expanded_lines = []
                
                for line in lines:
                    if initial_only:
                        # Convert tabs only at the beginning
                        prefix = ""
                        i = 0
                        while i < len(line) and (line[i] == ' ' or line[i] == '\t'):
                            if line[i] == '\t':
                                if tab_stops:
                                    # Find next tab stop
                                    next_stop = next((s for s in tab_stops if s > len(prefix)), tab_stops[-1])
                                    prefix += ' ' * (next_stop - len(prefix))
                                else:
                                    # Use fixed tab size
                                    prefix += ' ' * (tab_size - (len(prefix) % tab_size))
                            else:
                                prefix += ' '
                            i += 1
                        
                        expanded_lines.append(prefix + line[i:])
                    else:
                        # Convert all tabs
                        result_line = ""
                        for c in line:
                            if c == '\t':
                                if tab_stops:
                                    # Find next tab stop
                                    next_stop = next((s for s in tab_stops if s > len(result_line)), tab_stops[-1])
                                    result_line += ' ' * (next_stop - len(result_line))
                                else:
                                    # Use fixed tab size
                                    result_line += ' ' * (tab_size - (len(result_line) % tab_size))
                            else:
                                result_line += c
                        
                        expanded_lines.append(result_line)
                
                result.append('\n'.join(expanded_lines))
            
            return '\n'.join(result)
                
        except Exception as e:
            logger.error(f"Error in expand command: {e}")
            return f"expand: {str(e)}"
    
    @staticmethod
    def do_fold(fs, cwd, arg):
        """Wrap each input line to fit in specified width
        
        Usage: fold [OPTION]... [FILE]...
        Wrap input lines in each FILE, writing to standard output.
        
        Options:
          -b, --bytes         Count bytes rather than columns
          -s, --spaces        Break at spaces
          -w, --width=WIDTH   Use WIDTH columns instead of 80
        """
        try:
            args = shlex.split(arg)
            
            # Parse options
            count_bytes = False
            break_spaces = False
            width = 80
            files = []
            
            i = 0
            while i < len(args):
                if args[i] in ['-h', '--help']:
                    return TextProcessingCommands.do_fold.__doc__
                elif args[i] in ['-b', '--bytes']:
                    count_bytes = True
                elif args[i] in ['-s', '--spaces']:
                    break_spaces = True
                elif args[i].startswith('-w=') or args[i].startswith('--width='):
                    try:
                        width = int(args[i].split('=', 1)[1])
                    except ValueError:
                        return f"fold: invalid width: '{args[i].split('=', 1)[1]}'"
                elif args[i] in ['-w', '--width']:
                    if i + 1 < len(args):
                        try:
                            width = int(args[i + 1])
                            i += 1
                        except ValueError:
                            return f"fold: invalid width: '{args[i + 1]}'"
                    else:
                        return "fold: option requires an argument -- 'w'"
                else:
                    files.append(args[i])
                i += 1
            
            # Process files
            result = []
            
            for file in files or ['-']:
                if file == '-':
                    # Use stdin in a real implementation
                    # For this demo, use sample text
                    content = "This is a long line that needs to be folded into multiple lines based on the specified width. Let's see how well the folding works."
                else:
                    # Resolve path
                    path = os.path.join(cwd, file) if not os.path.isabs(file) else file
                    
                    # Check if file exists
                    if not fs.exists(path):
                        result.append(f"fold: {file}: No such file or directory")
                        continue
                    
                    # Check if it's a directory
                    if fs.is_dir(path):
                        result.append(f"fold: {file}: Is a directory")
                        continue
                    
                    # Read content
                    content = fs.read_file(path)
                
                # Process content
                lines = content.split('\n')
                folded_lines = []
                
                for line in lines:
                    if len(line) <= width:
                        folded_lines.append(line)
                        continue
                    
                    if count_bytes:
                        # Fold based on bytes
                        while line:
                            if break_spaces and len(line) > width:
                                # Find the last space within the width
                                last_space = line[:width].rfind(' ')
                                if last_space > 0:
                                    folded_lines.append(line[:last_space])
                                    line = line[last_space+1:]
                                else:
                                    folded_lines.append(line[:width])
                                    line = line[width:]
                            else:
                                folded_lines.append(line[:width])
                                line = line[width:]
                    else:
                        # Fold based on characters
                        current_pos = 0
                        current_line = ""
                        
                        for char in line:
                            current_line += char
                            current_pos += 1
                            
                            if current_pos >= width:
                                if break_spaces and ' ' in current_line:
                                    # Break at the last space
                                    last_space = current_line.rfind(' ')
                                    folded_lines.append(current_line[:last_space])
                                    current_line = current_line[last_space+1:]
                                    current_pos = len(current_line)
                                else:
                                    folded_lines.append(current_line)
                                    current_line = ""
                                    current_pos = 0
                        
                        if current_line:
                            folded_lines.append(current_line)
                
                result.append('\n'.join(folded_lines))
            
            return '\n'.join(result)
                
        except Exception as e:
            logger.error(f"Error in fold command: {e}")
            return f"fold: {str(e)}"

def register_commands(shell):
    """Register all text processing commands with the KOS shell."""
    
    # Add the uniq command
    def do_uniq(self, arg):
        """Filter adjacent matching lines from input
        
        Usage: uniq [OPTION]... [INPUT [OUTPUT]]
        Filter adjacent matching lines from INPUT (or standard input),
        writing to OUTPUT (or standard output).
        
        Options:
          -c, --count           Prefix lines by the number of occurrences
          -d, --repeated        Only print duplicate lines, one for each group
          -D                    Print all duplicate lines
          -f, --skip-fields=N   Avoid comparing the first N fields
          -i, --ignore-case     Ignore differences in case when comparing
          -s, --skip-chars=N    Avoid comparing the first N characters
          -u, --unique          Only print unique lines
          -z, --zero-terminated End lines with 0 byte, not newline
        """
        try:
            result = TextProcessingCommands.do_uniq(self.fs, self.fs.current_path, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in uniq command: {e}")
            print(f"uniq: {str(e)}")
    
    # Add the comm command
    def do_comm(self, arg):
        """Compare two sorted files line by line
        
        Usage: comm [OPTION]... FILE1 FILE2
        Compare sorted files FILE1 and FILE2 line by line.
        
        Options:
          -1              Suppress column 1 (lines unique to FILE1)
          -2              Suppress column 2 (lines unique to FILE2)
          -3              Suppress column 3 (lines that appear in both files)
          --output-delimiter=STR  Use STR as the output delimiter
          --check-order    Check that the input is correctly sorted
          --nocheck-order  Do not check that the input is correctly sorted
        """
        try:
            result = TextProcessingCommands.do_comm(self.fs, self.fs.current_path, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in comm command: {e}")
            print(f"comm: {str(e)}")
    
    # Add the expand command
    def do_expand(self, arg):
        """Convert tabs to spaces
        
        Usage: expand [OPTION]... [FILE]...
        Convert tabs in each FILE to spaces, writing to standard output.
        
        Options:
          -i, --initial       Do not convert tabs after non blanks
          -t, --tabs=N        Have tabs N characters apart, not 8
          -t, --tabs=LIST     Use comma separated list of tab positions
        """
        try:
            result = TextProcessingCommands.do_expand(self.fs, self.fs.current_path, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in expand command: {e}")
            print(f"expand: {str(e)}")
    
    # Add the fold command
    def do_fold(self, arg):
        """Wrap each input line to fit in specified width
        
        Usage: fold [OPTION]... [FILE]...
        Wrap input lines in each FILE, writing to standard output.
        
        Options:
          -b, --bytes         Count bytes rather than columns
          -s, --spaces        Break at spaces
          -w, --width=WIDTH   Use WIDTH columns instead of 80
        """
        try:
            result = TextProcessingCommands.do_fold(self.fs, self.fs.current_path, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in fold command: {e}")
            print(f"fold: {str(e)}")
    
    # Attach the command methods to the shell
    setattr(shell.__class__, 'do_uniq', do_uniq)
    setattr(shell.__class__, 'do_comm', do_comm)
    setattr(shell.__class__, 'do_expand', do_expand)
    setattr(shell.__class__, 'do_fold', do_fold)

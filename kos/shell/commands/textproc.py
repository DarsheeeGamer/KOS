"""
Text processing commands for KOS shell.
Implements various text manipulation utilities similar to Unix/Linux commands.
"""

import re
import os
import logging
from typing import List, Tuple, Optional, Dict, Any

logger = logging.getLogger('KOS.shell.textproc')

def cut_command(fs, args, cwd):
    """
    Remove sections from each line of files
    
    Usage: cut [OPTION]... [FILE]...
    Print selected parts of lines from each FILE to standard output.
    
    Options:
      -b, --bytes=LIST        Select only these bytes
      -c, --characters=LIST   Select only these characters
      -d, --delimiter=DELIM   Use DELIM instead of TAB for field delimiter
      -f, --fields=LIST       Select only these fields
      -s, --only-delimited    Do not print lines not containing delimiters
    """
    # Parse options
    select_bytes = None
    select_chars = None
    select_fields = None
    delimiter = '\t'  # Default delimiter is TAB
    only_delimited = False
    files = []
    
    i = 0
    while i < len(args):
        if args[i] in ['-h', '--help']:
            return cut_command.__doc__
        elif args[i].startswith('-b=') or args[i].startswith('--bytes='):
            select_bytes = args[i].split('=', 1)[1]
        elif args[i] in ['-b', '--bytes']:
            if i + 1 < len(args):
                select_bytes = args[i + 1]
                i += 1
            else:
                return "cut: option requires an argument -- 'b'"
        elif args[i].startswith('-c=') or args[i].startswith('--characters='):
            select_chars = args[i].split('=', 1)[1]
        elif args[i] in ['-c', '--characters']:
            if i + 1 < len(args):
                select_chars = args[i + 1]
                i += 1
            else:
                return "cut: option requires an argument -- 'c'"
        elif args[i].startswith('-d=') or args[i].startswith('--delimiter='):
            delimiter = args[i].split('=', 1)[1]
        elif args[i] in ['-d', '--delimiter']:
            if i + 1 < len(args):
                delimiter = args[i + 1]
                i += 1
            else:
                return "cut: option requires an argument -- 'd'"
        elif args[i].startswith('-f=') or args[i].startswith('--fields='):
            select_fields = args[i].split('=', 1)[1]
        elif args[i] in ['-f', '--fields']:
            if i + 1 < len(args):
                select_fields = args[i + 1]
                i += 1
            else:
                return "cut: option requires an argument -- 'f'"
        elif args[i] in ['-s', '--only-delimited']:
            only_delimited = True
        else:
            files.append(args[i])
        i += 1
            
    # Validate options
    option_count = sum(x is not None for x in [select_bytes, select_chars, select_fields])
    if option_count == 0:
        return "cut: you must specify a list of bytes, characters, or fields"
    elif option_count > 1:
        return "cut: only one type of list may be specified"
            
    if not files:
        return "cut: missing file operand"
            
    # Parse the ranges (for bytes, characters, or fields)
    def parse_ranges(range_str):
        ranges = []
        for part in range_str.split(','):
            if '-' in part:
                start, end = part.split('-', 1)
                start = int(start) if start else 1  # Empty start means from beginning
                end = int(end) if end else float('inf')  # Empty end means till end
                ranges.append((start, end))
            else:
                # Single position
                pos = int(part)
                ranges.append((pos, pos))
        return ranges
            
    # Function to extract bytes/characters based on ranges
    def extract_by_position(line, ranges):
        result = []
        for start, end in ranges:
            # Adjust for 1-based indexing to 0-based
            start_idx = start - 1
            end_idx = min(end, len(line))  # Don't go beyond the string length
            
            # Handle ranges beyond the line length
            if start_idx >= len(line):
                continue
                
            # Extract the characters in the range
            result.append(line[start_idx:end_idx])
        return ''.join(result)
            
    # Function to extract fields based on delimiter and ranges
    def extract_fields(line, delimiter, ranges, only_delimited):
        # Skip lines without the delimiter if only_delimited is True
        if only_delimited and delimiter not in line:
            return None
            
        fields = line.split(delimiter)
        result = []
        
        for start, end in ranges:
            # Adjust for 1-based indexing to 0-based
            start_idx = start - 1
            end_idx = min(end, len(fields))  # Don't go beyond the number of fields
            
            # Handle ranges beyond the number of fields
            if start_idx >= len(fields):
                continue
                
            # Extract the fields in the range
            result.extend(fields[start_idx:end_idx])
            
        return delimiter.join(result)
            
    # Process each file
    output_lines = []
    
    for filename in files:
        # Resolve path
        path = os.path.join(cwd, filename) if not os.path.isabs(filename) else filename
        
        # Check if file exists
        if not fs.exists(path):
            output_lines.append(f"cut: {filename}: No such file or directory")
            continue
            
        # Check if it's a directory
        if fs.is_dir(path):
            output_lines.append(f"cut: {filename}: Is a directory")
            continue
            
        try:
            content = fs.read_file(path)
            lines = content.split('\n')
            
            for line in lines:
                if select_bytes is not None:
                    ranges = parse_ranges(select_bytes)
                    result = extract_by_position(line.encode('utf-8'), ranges).decode('utf-8', errors='replace')
                    output_lines.append(result)
                elif select_chars is not None:
                    ranges = parse_ranges(select_chars)
                    result = extract_by_position(line, ranges)
                    output_lines.append(result)
                elif select_fields is not None:
                    ranges = parse_ranges(select_fields)
                    result = extract_fields(line, delimiter, ranges, only_delimited)
                    if result is not None:  # May be None if line is skipped due to only_delimited
                        output_lines.append(result)
                        
        except Exception as e:
            output_lines.append(f"cut: {filename}: {str(e)}")
    
    return '\n'.join(output_lines)

def paste_command(fs, args, cwd):
    """
    Merge lines of files
    
    Usage: paste [OPTION]... [FILE]...
    Write lines consisting of the sequentially corresponding lines from
    each FILE, separated by TABs, to standard output.
    
    Options:
      -d, --delimiters=LIST   Use characters from LIST instead of TABs
      -s, --serial            Paste one file at a time instead of in parallel
    """
    # Parse options
    delimiters = '\t'  # Default delimiter is TAB
    serial = False
    files = []
    
    i = 0
    while i < len(args):
        if args[i] in ['-h', '--help']:
            return paste_command.__doc__
        elif args[i].startswith('-d=') or args[i].startswith('--delimiters='):
            delimiters = args[i].split('=', 1)[1]
        elif args[i] in ['-d', '--delimiters']:
            if i + 1 < len(args):
                delimiters = args[i + 1]
                i += 1
            else:
                return "paste: option requires an argument -- 'd'"
        elif args[i] in ['-s', '--serial']:
            serial = True
        else:
            files.append(args[i])
        i += 1
    
    if not files:
        return "paste: missing file operand"
    
    # Read all files
    file_contents = []
    for filename in files:
        # Resolve path
        path = os.path.join(cwd, filename) if not os.path.isabs(filename) else filename
        
        # Check if file exists
        if not fs.exists(path):
            return f"paste: {filename}: No such file or directory"
        
        # Check if it's a directory
        if fs.is_dir(path):
            return f"paste: {filename}: Is a directory"
        
        try:
            content = fs.read_file(path)
            lines = content.split('\n')
            file_contents.append(lines)
        except Exception as e:
            return f"paste: {filename}: {str(e)}"
    
    # Prepare delimiters cycle
    delim_cycle = [delimiters[i % len(delimiters)] for i in range(max(1, len(files) - 1))]
    
    # Process files
    output_lines = []
    
    if serial:
        # Process one file at a time
        for lines in file_contents:
            if not lines:
                continue
            
            result = lines[0]
            for i in range(1, len(lines)):
                delimiter = delim_cycle[(i - 1) % len(delim_cycle)]
                result += delimiter + lines[i]
            
            output_lines.append(result)
    else:
        # Process files in parallel
        max_lines = max(len(lines) for lines in file_contents)
        
        for line_idx in range(max_lines):
            line_parts = []
            
            for file_idx, lines in enumerate(file_contents):
                if line_idx < len(lines):
                    line_parts.append(lines[line_idx])
                else:
                    line_parts.append('')
            
            # Join line parts with delimiters
            result = line_parts[0]
            for i in range(1, len(line_parts)):
                delimiter = delim_cycle[(i - 1) % len(delim_cycle)]
                result += delimiter + line_parts[i]
            
            output_lines.append(result)
    
    return '\n'.join(output_lines)

def tr_command(fs, args, cwd):
    """
    Translate or delete characters
    
    Usage: tr [OPTION]... SET1 [SET2]
    Translate, squeeze, and/or delete characters from standard input,
    writing to standard output.
    
    Options:
      -c, --complement    Use the complement of SET1
      -d, --delete        Delete characters in SET1, do not translate
      -s, --squeeze-repeats  Replace each sequence of a repeated character that
                             is listed in the last specified SET, with a single
                             occurrence of that character
    
    SET1 and SET2 are character ranges like [a-z] or special characters.
    """
    # Parse options
    complement = False
    delete = False
    squeeze = False
    sets = []
    
    i = 0
    while i < len(args):
        if args[i] in ['-h', '--help']:
            return tr_command.__doc__
        elif args[i] in ['-c', '--complement']:
            complement = True
        elif args[i] in ['-d', '--delete']:
            delete = True
        elif args[i] in ['-s', '--squeeze-repeats']:
            squeeze = True
        else:
            sets.append(args[i])
        i += 1
    
    if not sets:
        return "tr: missing operand\nTry 'tr --help' for more information."
    
    if len(sets) > 2:
        return "tr: extra operand\nTry 'tr --help' for more information."
    
    # Expand character ranges in sets
    def expand_set(s):
        result = []
        i = 0
        while i < len(s):
            if i + 2 < len(s) and s[i+1] == '-':
                # Range like a-z
                start = ord(s[i])
                end = ord(s[i+2])
                result.extend(chr(c) for c in range(start, end + 1))
                i += 3
            else:
                result.append(s[i])
                i += 1
        return ''.join(result)
    
    set1 = expand_set(sets[0])
    set2 = expand_set(sets[1]) if len(sets) > 1 else ''
    
    # Implement complement of set1 if needed
    if complement:
        all_chars = ''.join(chr(i) for i in range(256))
        set1 = ''.join(c for c in all_chars if c not in set1)
    
    # Read from stdin (not fully implemented in this demo)
    # In a real implementation, this would read from actual stdin
    stdin_content = "This is sample input for tr command demonstration."
    
    # Process the input
    output = []
    
    for char in stdin_content:
        if delete:
            if char not in set1:
                output.append(char)
        else:
            if char in set1:
                idx = set1.index(char)
                if idx < len(set2):
                    output.append(set2[idx])
                elif delete:
                    # Delete if no mapping in set2
                    continue
                else:
                    # Use the last character of set2 for all remaining characters
                    output.append(set2[-1] if set2 else '')
            else:
                output.append(char)
    
    result = ''.join(output)
    
    # Apply squeezing if needed
    if squeeze:
        squeeze_set = set2 if len(sets) > 1 else set1
        squeezed = []
        
        for char in result:
            if not squeezed or char != squeezed[-1] or char not in squeeze_set:
                squeezed.append(char)
        
        result = ''.join(squeezed)
    
    return result

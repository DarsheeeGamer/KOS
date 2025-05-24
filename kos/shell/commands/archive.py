"""
Archive and Compression Commands for KOS shell.

This module implements various archiving and compression utilities similar to
common Unix/Linux commands like tar, gzip, zip, etc.
"""

import os
import re
import shlex
import logging
import zipfile
import gzip
import io
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple

logger = logging.getLogger('KOS.shell.archive')

class ArchiveCommands:
    """Implementation of archive and compression commands for KOS shell."""
    
    @staticmethod
    def do_zip(fs, cwd, arg):
        """Package and compress files
        
        Usage: zip [options] zipfile files...
        Package and compress files into a ZIP archive.
        
        Options:
          -r       Recursively include files in directories
          -u       Update existing entries if newer on disk
          -q       Quiet mode; suppress informational messages
          -v       Verbose mode; show file details
          -j       Junk (don't record) directory names
          -d       Delete entries in zipfile
          -0 to -9  Compression level (0=none, 9=best)
        
        Examples:
          zip archive.zip file1.txt file2.txt     # Create zip with two files
          zip -r archive.zip directory/           # Recursively add directory
        """
        try:
            args = shlex.split(arg)
            
            # Parse options
            recursive = False
            update = False
            quiet = False
            verbose = False
            junk_dirs = False
            delete_entries = False
            compression_level = 6  # Default compression level
            zipfile_name = None
            files = []
            
            i = 0
            while i < len(args):
                if args[i] in ['-h', '--help']:
                    return ArchiveCommands.do_zip.__doc__
                elif args[i] == '-r':
                    recursive = True
                elif args[i] == '-u':
                    update = True
                elif args[i] == '-q':
                    quiet = True
                elif args[i] == '-v':
                    verbose = True
                elif args[i] == '-j':
                    junk_dirs = True
                elif args[i] == '-d':
                    delete_entries = True
                elif re.match(r'-[0-9]$', args[i]):
                    compression_level = int(args[i][1])
                elif zipfile_name is None:
                    zipfile_name = args[i]
                else:
                    files.append(args[i])
                i += 1
            
            if zipfile_name is None:
                return "zip: missing zipfile argument"
            
            if not files:
                return "zip: no files specified"
            
            # Resolve zipfile path
            zip_path = os.path.join(cwd, zipfile_name) if not os.path.isabs(zipfile_name) else zipfile_name
            
            # Function to collect files recursively
            def collect_files(base_path, rel_path='', file_list=None):
                if file_list is None:
                    file_list = []
                
                full_path = os.path.join(base_path, rel_path) if rel_path else base_path
                
                if not fs.exists(full_path):
                    if not quiet:
                        file_list.append(f"zip warning: {full_path} does not exist")
                    return file_list
                
                if fs.is_dir(full_path):
                    if recursive:
                        for item in fs.list_dir(full_path):
                            item_rel_path = os.path.join(rel_path, item) if rel_path else item
                            collect_files(base_path, item_rel_path, file_list)
                else:
                    file_list.append((full_path, rel_path if not junk_dirs else os.path.basename(full_path)))
                
                return file_list
            
            # Collect all files to add/update
            all_files = []
            warnings = []
            
            for file_pattern in files:
                # Resolve path
                file_path = os.path.join(cwd, file_pattern) if not os.path.isabs(file_pattern) else file_pattern
                
                # Handle wildcards (simple implementation)
                if '*' in file_pattern or '?' in file_pattern:
                    # This is a simplified wildcard handling
                    # In a real implementation, use more robust glob pattern matching
                    base_dir = os.path.dirname(file_path) or cwd
                    pattern = os.path.basename(file_path)
                    
                    pattern_regex = pattern.replace('.', '\\.').replace('*', '.*').replace('?', '.')
                    
                    found = False
                    for item in fs.list_dir(base_dir):
                        if re.match(pattern_regex, item):
                            found = True
                            item_path = os.path.join(base_dir, item)
                            result = collect_files(item_path)
                            
                            # Separate warnings from files
                            for r in result:
                                if isinstance(r, str):  # Warning message
                                    warnings.append(r)
                                else:  # File entry
                                    all_files.append(r)
                    
                    if not found and not quiet:
                        warnings.append(f"zip warning: No files found matching {file_pattern}")
                else:
                    result = collect_files(file_path)
                    
                    # Separate warnings from files
                    for r in result:
                        if isinstance(r, str):  # Warning message
                            warnings.append(r)
                        else:  # File entry
                            all_files.append(r)
            
            # Create or update the ZIP file
            if delete_entries:
                # Implement deletion logic (not fully implemented)
                return "zip: -d option not implemented yet"
            
            # Check if zipfile already exists
            zipfile_exists = fs.exists(zip_path)
            
            # Mode: 'w' for new file, 'a' for update
            mode = 'a' if zipfile_exists and update else 'w'
            
            # Create a memory buffer for the ZIP file
            zip_buffer = io.BytesIO()
            
            try:
                with zipfile.ZipFile(zip_buffer, mode, compression=zipfile.ZIP_DEFLATED, 
                                     compresslevel=compression_level) as zipf:
                    # If updating, need to copy existing content first
                    if zipfile_exists and update and mode == 'a':
                        existing_content = fs.read_file(zip_path, binary=True)
                        existing_buffer = io.BytesIO(existing_content)
                        
                        with zipfile.ZipFile(existing_buffer, 'r') as existing_zip:
                            for info in existing_zip.infolist():
                                zipf.writestr(info, existing_zip.read(info.filename))
                    
                    # Add files to ZIP
                    for file_path, archive_path in all_files:
                        try:
                            file_content = fs.read_file(file_path, binary=True)
                            
                            # Add file to ZIP
                            if verbose and not quiet:
                                file_size = len(file_content)
                                print(f"adding: {archive_path} ({file_size} bytes)")
                            
                            zipf.writestr(archive_path, file_content)
                            
                        except Exception as e:
                            warnings.append(f"zip: error adding {file_path}: {str(e)}")
            
            except Exception as e:
                return f"zip: error creating zipfile: {str(e)}"
            
            # Write the ZIP file to the filesystem
            try:
                fs.write_file(zip_path, zip_buffer.getvalue(), binary=True)
            except Exception as e:
                return f"zip: error writing zipfile: {str(e)}"
            
            # Output results
            if not quiet:
                output = []
                for warning in warnings:
                    output.append(warning)
                
                if verbose:
                    output.append(f"Archive: {zipfile_name}")
                    output.append(f"Total {len(all_files)} files added/updated")
                else:
                    output.append(f"adding: {len(all_files)} files to {zipfile_name}")
                
                return "\n".join(output)
            
            return ""
                
        except Exception as e:
            logger.error(f"Error in zip command: {e}")
            return f"zip: {str(e)}"
    
    @staticmethod
    def do_unzip(fs, cwd, arg):
        """Extract files from a ZIP archive
        
        Usage: unzip [options] zipfile [file...] [-d dir]
        Extract files from a ZIP archive.
        
        Options:
          -l       List archive contents without extracting
          -t       Test archive integrity
          -v       Verbose mode/list contents verbosely
          -q       Quiet mode; suppress informational messages
          -o       Overwrite existing files without prompting
          -n       Never overwrite existing files
          -d dir   Extract files into dir
        
        Examples:
          unzip archive.zip             # Extract all files
          unzip -l archive.zip          # List contents without extracting
          unzip archive.zip -d target/  # Extract to target directory
        """
        try:
            args = shlex.split(arg)
            
            # Parse options
            list_only = False
            test_only = False
            verbose = False
            quiet = False
            overwrite = None  # None: prompt, True: always, False: never
            extract_dir = None
            zipfile_name = None
            specific_files = []
            
            i = 0
            while i < len(args):
                if args[i] in ['-h', '--help']:
                    return ArchiveCommands.do_unzip.__doc__
                elif args[i] == '-l':
                    list_only = True
                elif args[i] == '-t':
                    test_only = True
                elif args[i] == '-v':
                    verbose = True
                elif args[i] == '-q':
                    quiet = True
                elif args[i] == '-o':
                    overwrite = True
                elif args[i] == '-n':
                    overwrite = False
                elif args[i] == '-d':
                    if i + 1 < len(args):
                        extract_dir = args[i + 1]
                        i += 1
                    else:
                        return "unzip: option requires an argument -- 'd'"
                elif zipfile_name is None:
                    zipfile_name = args[i]
                else:
                    specific_files.append(args[i])
                i += 1
            
            if zipfile_name is None:
                return "unzip: missing zipfile argument"
            
            # Resolve zipfile path
            zip_path = os.path.join(cwd, zipfile_name) if not os.path.isabs(zipfile_name) else zipfile_name
            
            # Check if zipfile exists
            if not fs.exists(zip_path):
                return f"unzip: cannot find {zipfile_name}"
            
            # Resolve extract directory
            if extract_dir:
                extract_path = os.path.join(cwd, extract_dir) if not os.path.isabs(extract_dir) else extract_dir
                
                # Create extract directory if it doesn't exist
                if not fs.exists(extract_path):
                    try:
                        fs.mkdir(extract_path)
                    except Exception as e:
                        return f"unzip: cannot create directory {extract_dir}: {str(e)}"
            else:
                extract_path = cwd
            
            # Read the ZIP file
            try:
                zip_content = fs.read_file(zip_path, binary=True)
                zip_buffer = io.BytesIO(zip_content)
                
                with zipfile.ZipFile(zip_buffer, 'r') as zipf:
                    # Test the archive if requested
                    if test_only:
                        test_result = zipf.testzip()
                        if test_result:
                            return f"unzip: first bad file: {test_result}"
                        else:
                            return f"No errors detected in {zipfile_name}"
                    
                    # Get file list
                    file_list = zipf.infolist()
                    
                    # Filter specific files if requested
                    if specific_files:
                        file_list = [f for f in file_list if f.filename in specific_files]
                    
                    # List archive contents if requested
                    if list_only:
                        result = []
                        if not quiet:
                            result.append(f"Archive: {zipfile_name}")
                            if verbose:
                                result.append("  Length     Date    Time    Name")
                                result.append("  ------     ----    ----    ----")
                                
                                for info in file_list:
                                    date = datetime(*info.date_time).strftime("%Y-%m-%d")
                                    time = datetime(*info.date_time).strftime("%H:%M:%S")
                                    result.append(f"  {info.file_size:6d}  {date}  {time}  {info.filename}")
                                
                                result.append(f"  ------                   -------")
                                total_size = sum(info.file_size for info in file_list)
                                result.append(f"  {total_size:6d}                   {len(file_list)} files")
                            else:
                                for info in file_list:
                                    result.append(info.filename)
                        
                        return "\n".join(result)
                    
                    # Extract files
                    extracted_files = []
                    skipped_files = []
                    
                    for info in file_list:
                        # Resolve target path
                        target_path = os.path.join(extract_path, info.filename)
                        
                        # Create directories if necessary
                        if info.filename.endswith('/'):
                            # Directory entry
                            if not fs.exists(target_path):
                                try:
                                    fs.mkdir(target_path)
                                    if verbose and not quiet:
                                        print(f"creating: {info.filename}")
                                    extracted_files.append(info.filename)
                                except Exception as e:
                                    if not quiet:
                                        print(f"unzip: cannot create directory {info.filename}: {str(e)}")
                            continue
                        
                        # Create parent directories if they don't exist
                        parent_dir = os.path.dirname(target_path)
                        if parent_dir and not fs.exists(parent_dir):
                            try:
                                fs.mkdir(parent_dir, recursive=True)
                                if verbose and not quiet:
                                    print(f"creating: {os.path.dirname(info.filename)}/")
                            except Exception as e:
                                if not quiet:
                                    print(f"unzip: cannot create directory {os.path.dirname(info.filename)}: {str(e)}")
                                continue
                        
                        # Check if file exists
                        if fs.exists(target_path):
                            if overwrite is False:
                                # Skip existing files
                                if not quiet:
                                    print(f"skipping: {info.filename} already exists")
                                skipped_files.append(info.filename)
                                continue
                            elif overwrite is None:
                                # Prompt for overwrite (not fully implemented)
                                # In a real implementation, this would prompt the user
                                # For now, we'll just skip
                                if not quiet:
                                    print(f"skipping: {info.filename} already exists")
                                skipped_files.append(info.filename)
                                continue
                        
                        # Extract the file
                        try:
                            file_content = zipf.read(info.filename)
                            fs.write_file(target_path, file_content, binary=True)
                            
                            if verbose and not quiet:
                                print(f"inflating: {info.filename}")
                            elif not quiet:
                                print(f"extracting: {info.filename}")
                            
                            extracted_files.append(info.filename)
                            
                        except Exception as e:
                            if not quiet:
                                print(f"unzip: error extracting {info.filename}: {str(e)}")
                    
                    # Output summary
                    if not quiet and not verbose:
                        return f"Extracted {len(extracted_files)} files" + \
                               (f", skipped {len(skipped_files)} existing files" if skipped_files else "")
                    
                    return ""
                
            except zipfile.BadZipFile:
                return f"unzip: {zipfile_name} is not a valid ZIP file"
            except Exception as e:
                return f"unzip: error processing {zipfile_name}: {str(e)}"
                
        except Exception as e:
            logger.error(f"Error in unzip command: {e}")
            return f"unzip: {str(e)}"

    @staticmethod
    def do_gzip(fs, cwd, arg):
        """Compress files using gzip format
        
        Usage: gzip [options] [file...]
        Compress or decompress files using the gzip format.
        
        Options:
          -d, --decompress    Decompress files
          -k, --keep          Keep (don't delete) input files
          -l, --list          List compressed file contents
          -v, --verbose       Verbose mode
          -1 to -9            Compression level (1=fast, 9=best)
          -c, --stdout        Write to standard output, keep input files
        
        Examples:
          gzip file.txt           # Compress file.txt to file.txt.gz
          gzip -d file.txt.gz     # Decompress file.txt.gz
          gzip -l file.txt.gz     # List information about file.txt.gz
        """
        try:
            args = shlex.split(arg)
            
            # Parse options
            decompress = False
            keep_input = False
            list_only = False
            verbose = False
            to_stdout = False
            compression_level = 6  # Default compression level
            files = []
            
            i = 0
            while i < len(args):
                if args[i] in ['-h', '--help']:
                    return ArchiveCommands.do_gzip.__doc__
                elif args[i] in ['-d', '--decompress']:
                    decompress = True
                elif args[i] in ['-k', '--keep']:
                    keep_input = True
                elif args[i] in ['-l', '--list']:
                    list_only = True
                elif args[i] in ['-v', '--verbose']:
                    verbose = True
                elif args[i] in ['-c', '--stdout']:
                    to_stdout = True
                    keep_input = True  # Implicitly keep input files
                elif re.match(r'-[1-9]$', args[i]):
                    compression_level = int(args[i][1])
                else:
                    files.append(args[i])
                i += 1
            
            if not files:
                return "gzip: missing file operand"
            
            results = []
            
            for filename in files:
                # Resolve file path
                file_path = os.path.join(cwd, filename) if not os.path.isabs(filename) else filename
                
                # Check if file exists
                if not fs.exists(file_path):
                    results.append(f"gzip: {filename}: No such file or directory")
                    continue
                
                # Check if it's a directory
                if fs.is_dir(file_path):
                    results.append(f"gzip: {filename}: Is a directory")
                    continue
                
                try:
                    if list_only:
                        # List information about gzip file
                        if not filename.endswith('.gz'):
                            results.append(f"gzip: {filename}: not in gzip format")
                            continue
                        
                        try:
                            content = fs.read_file(file_path, binary=True)
                            with gzip.GzipFile(fileobj=io.BytesIO(content)) as f:
                                # Get uncompressed size
                                f.seek(0, io.SEEK_END)
                                uncompressed_size = f.tell()
                                
                                # Get compressed size
                                compressed_size = len(content)
                                
                                # Calculate ratio
                                ratio = 100.0 - (compressed_size * 100.0 / uncompressed_size) if uncompressed_size > 0 else 0
                                
                                results.append(f"compressed        uncompressed  ratio   name")
                                results.append(f"{compressed_size:10d}      {uncompressed_size:10d}  {ratio:6.1f}%   {filename}")
                        except Exception as e:
                            results.append(f"gzip: {filename}: {str(e)}")
                        
                    elif decompress:
                        # Decompress file
                        if not filename.endswith('.gz'):
                            results.append(f"gzip: {filename} does not have .gz suffix")
                            continue
                        
                        content = fs.read_file(file_path, binary=True)
                        try:
                            with gzip.GzipFile(fileobj=io.BytesIO(content)) as f:
                                decompressed_data = f.read()
                            
                            # Determine output filename
                            output_filename = filename[:-3]  # Remove .gz suffix
                            output_path = os.path.join(cwd, output_filename) if not os.path.isabs(output_filename) else output_filename
                            
                            if to_stdout:
                                # Print to stdout
                                results.append(decompressed_data.decode('utf-8', errors='replace'))
                            else:
                                # Write to file
                                fs.write_file(output_path, decompressed_data, binary=True)
                                
                                if verbose:
                                    results.append(f"gzip: {filename}: {len(content)} -> {len(decompressed_data)} bytes")
                                
                                # Delete input file if not keeping
                                if not keep_input:
                                    fs.rm(file_path)
                        except Exception as e:
                            results.append(f"gzip: {filename}: {str(e)}")
                    
                    else:
                        # Compress file
                        content = fs.read_file(file_path, binary=True)
                        
                        out = io.BytesIO()
                        with gzip.GzipFile(fileobj=out, mode='wb', compresslevel=compression_level) as f:
                            f.write(content)
                        
                        compressed_data = out.getvalue()
                        
                        # Determine output filename
                        output_filename = filename + '.gz'
                        output_path = os.path.join(cwd, output_filename) if not os.path.isabs(output_filename) else output_filename
                        
                        if to_stdout:
                            # Not really printing binary data to stdout in this implementation
                            results.append(f"gzip: binary data would be written to stdout")
                        else:
                            # Write to file
                            fs.write_file(output_path, compressed_data, binary=True)
                            
                            if verbose:
                                results.append(f"gzip: {filename}: {len(content)} -> {len(compressed_data)} bytes")
                            
                            # Delete input file if not keeping
                            if not keep_input:
                                fs.rm(file_path)
                
                except Exception as e:
                    results.append(f"gzip: {filename}: {str(e)}")
            
            return "\n".join(results)
                
        except Exception as e:
            logger.error(f"Error in gzip command: {e}")
            return f"gzip: {str(e)}"

def register_commands(shell):
    """Register all archive commands with the KOS shell."""
    
    # Add the zip command
    def do_zip(self, arg):
        """Package and compress files
        
        Usage: zip [options] zipfile files...
        Package and compress files into a ZIP archive.
        
        Options:
          -r       Recursively include files in directories
          -u       Update existing entries if newer on disk
          -q       Quiet mode; suppress informational messages
          -v       Verbose mode; show file details
          -j       Junk (don't record) directory names
          -d       Delete entries in zipfile
          -0 to -9  Compression level (0=none, 9=best)
        """
        try:
            result = ArchiveCommands.do_zip(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in zip command: {e}")
            print(f"zip: {str(e)}")
    
    # Add the unzip command
    def do_unzip(self, arg):
        """Extract files from a ZIP archive
        
        Usage: unzip [options] zipfile [file...] [-d dir]
        Extract files from a ZIP archive.
        
        Options:
          -l       List archive contents without extracting
          -t       Test archive integrity
          -v       Verbose mode/list contents verbosely
          -q       Quiet mode; suppress informational messages
          -o       Overwrite existing files without prompting
          -n       Never overwrite existing files
          -d dir   Extract files into dir
        """
        try:
            result = ArchiveCommands.do_unzip(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in unzip command: {e}")
            print(f"unzip: {str(e)}")
    
    # Add the gzip command
    def do_gzip(self, arg):
        """Compress files using gzip format
        
        Usage: gzip [options] [file...]
        Compress or decompress files using the gzip format.
        
        Options:
          -d, --decompress    Decompress files
          -k, --keep          Keep (don't delete) input files
          -l, --list          List compressed file contents
          -v, --verbose       Verbose mode
          -1 to -9            Compression level (1=fast, 9=best)
          -c, --stdout        Write to standard output, keep input files
        """
        try:
            result = ArchiveCommands.do_gzip(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in gzip command: {e}")
            print(f"gzip: {str(e)}")
    
    # Attach the command methods to the shell
    setattr(shell.__class__, 'do_zip', do_zip)
    setattr(shell.__class__, 'do_unzip', do_unzip)
    setattr(shell.__class__, 'do_gzip', do_gzip)

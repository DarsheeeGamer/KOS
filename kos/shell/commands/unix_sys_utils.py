"""
Unix-like System Utilities for KOS Shell

This module provides Linux/Unix-like system administration commands for KOS.
"""

import os
import sys
import time
import logging
import platform
import socket
import psutil
import datetime
from typing import Dict, List, Any, Optional, Union

# Import KOS components
from kos.layer import klayer
from kos.advlayer import kadvlayer

# Set up logging
logger = logging.getLogger('KOS.shell.commands.unix_sys_utils')

class UnixSystemUtilities:
    """Unix-like system commands for KOS shell"""
    
    @staticmethod
    def do_uname(fs, cwd, arg):
        """
        Print system information
        
        Usage: uname [options]
        
        Options:
          -a, --all           Print all information
          -s, --kernel-name   Print the kernel name
          -n, --nodename      Print the network node hostname
          -r, --kernel-release Print the kernel release
          -v, --kernel-version Print the kernel version
          -m, --machine       Print the machine hardware name
          -p, --processor     Print the processor type
          -i, --hardware-platform Print the hardware platform
          -o, --operating-system Print the operating system
        """
        args = arg.split()
        
        # Parse options
        show_all = False
        show_kernel_name = False
        show_nodename = False
        show_kernel_release = False
        show_kernel_version = False
        show_machine = False
        show_processor = False
        show_hardware_platform = False
        show_operating_system = False
        
        # Process arguments
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                if args[i] in ['-a', '--all']:
                    show_all = True
                elif args[i] in ['-s', '--kernel-name']:
                    show_kernel_name = True
                elif args[i] in ['-n', '--nodename']:
                    show_nodename = True
                elif args[i] in ['-r', '--kernel-release']:
                    show_kernel_release = True
                elif args[i] in ['-v', '--kernel-version']:
                    show_kernel_version = True
                elif args[i] in ['-m', '--machine']:
                    show_machine = True
                elif args[i] in ['-p', '--processor']:
                    show_processor = True
                elif args[i] in ['-i', '--hardware-platform']:
                    show_hardware_platform = True
                elif args[i] in ['-o', '--operating-system']:
                    show_operating_system = True
                else:
                    # Process combined options
                    for c in args[i][1:]:
                        if c == 'a':
                            show_all = True
                        elif c == 's':
                            show_kernel_name = True
                        elif c == 'n':
                            show_nodename = True
                        elif c == 'r':
                            show_kernel_release = True
                        elif c == 'v':
                            show_kernel_version = True
                        elif c == 'm':
                            show_machine = True
                        elif c == 'p':
                            show_processor = True
                        elif c == 'i':
                            show_hardware_platform = True
                        elif c == 'o':
                            show_operating_system = True
            i += 1
        
        # If no options specified, default to -s
        if not (show_all or show_kernel_name or show_nodename or show_kernel_release or
                show_kernel_version or show_machine or show_processor or
                show_hardware_platform or show_operating_system):
            show_kernel_name = True
        
        # Get system information
        kernel_name = "KOS"
        nodename = socket.gethostname()
        kernel_release = "1.0"  # KOS version
        kernel_version = "#1 SMP " + datetime.datetime.now().strftime("%a %b %d %H:%M:%S %Z %Y")
        machine = platform.machine()
        processor = platform.processor()
        hardware_platform = platform.machine()
        operating_system = "KOS"
        
        # Format output
        output = []
        
        if show_all:
            output = [
                kernel_name,
                nodename,
                kernel_release,
                kernel_version,
                machine,
                processor,
                hardware_platform,
                operating_system
            ]
        else:
            if show_kernel_name:
                output.append(kernel_name)
            if show_nodename:
                output.append(nodename)
            if show_kernel_release:
                output.append(kernel_release)
            if show_kernel_version:
                output.append(kernel_version)
            if show_machine:
                output.append(machine)
            if show_processor:
                output.append(processor)
            if show_hardware_platform:
                output.append(hardware_platform)
            if show_operating_system:
                output.append(operating_system)
        
        return " ".join(output)
    
    @staticmethod
    def do_uptime(fs, cwd, arg):
        """
        Tell how long the system has been running
        
        Usage: uptime [options]
        
        Options:
          -p, --pretty        Show uptime in pretty format
          -s, --since         System up since
        """
        args = arg.split()
        
        # Parse options
        pretty = False
        since = False
        
        # Process arguments
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                if args[i] in ['-p', '--pretty']:
                    pretty = True
                elif args[i] in ['-s', '--since']:
                    since = True
                else:
                    # Process combined options
                    for c in args[i][1:]:
                        if c == 'p':
                            pretty = True
                        elif c == 's':
                            since = True
            i += 1
        
        # Get uptime
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        
        # Format output
        if since:
            boot_datetime = datetime.datetime.fromtimestamp(boot_time)
            return boot_datetime.strftime("%Y-%m-%d %H:%M:%S")
        elif pretty:
            days, remainder = divmod(uptime_seconds, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            output = "up "
            if days > 0:
                output += f"{int(days)} {'day' if days == 1 else 'days'}, "
            
            if hours > 0:
                output += f"{int(hours)} {'hour' if hours == 1 else 'hours'}, "
            
            output += f"{int(minutes)} {'minute' if minutes == 1 else 'minutes'}"
            
            return output
        else:
            # Standard format
            current_time = time.strftime("%H:%M:%S")
            days, remainder = divmod(uptime_seconds, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            # Get load averages
            load_avgs = psutil.getloadavg()
            
            # Get user count
            user_count = len(psutil.users())
            
            return f"{current_time} up {int(days)} days, {int(hours)}:{int(minutes):02d}, {user_count} {'user' if user_count == 1 else 'users'}, load average: {load_avgs[0]:.2f}, {load_avgs[1]:.2f}, {load_avgs[2]:.2f}"
    
    @staticmethod
    def do_free(fs, cwd, arg):
        """
        Display amount of free and used memory in the system
        
        Usage: free [options]
        
        Options:
          -b, --bytes         Show output in bytes
          -k, --kilo          Show output in kilobytes
          -m, --mega          Show output in megabytes
          -g, --giga          Show output in gigabytes
          -h, --human         Show human-readable output
          -t, --total         Show total for RAM + swap
        """
        args = arg.split()
        
        # Parse options
        bytes_format = False
        kilo_format = False
        mega_format = True  # Default
        giga_format = False
        human_format = False
        show_total = False
        
        # Process arguments
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                if args[i] in ['-b', '--bytes']:
                    bytes_format = True
                    kilo_format = False
                    mega_format = False
                    giga_format = False
                    human_format = False
                elif args[i] in ['-k', '--kilo']:
                    bytes_format = False
                    kilo_format = True
                    mega_format = False
                    giga_format = False
                    human_format = False
                elif args[i] in ['-m', '--mega']:
                    bytes_format = False
                    kilo_format = False
                    mega_format = True
                    giga_format = False
                    human_format = False
                elif args[i] in ['-g', '--giga']:
                    bytes_format = False
                    kilo_format = False
                    mega_format = False
                    giga_format = True
                    human_format = False
                elif args[i] in ['-h', '--human']:
                    bytes_format = False
                    kilo_format = False
                    mega_format = False
                    giga_format = False
                    human_format = True
                elif args[i] in ['-t', '--total']:
                    show_total = True
                else:
                    # Process combined options
                    for c in args[i][1:]:
                        if c == 'b':
                            bytes_format = True
                            kilo_format = False
                            mega_format = False
                            giga_format = False
                            human_format = False
                        elif c == 'k':
                            bytes_format = False
                            kilo_format = True
                            mega_format = False
                            giga_format = False
                            human_format = False
                        elif c == 'm':
                            bytes_format = False
                            kilo_format = False
                            mega_format = True
                            giga_format = False
                            human_format = False
                        elif c == 'g':
                            bytes_format = False
                            kilo_format = False
                            mega_format = False
                            giga_format = True
                            human_format = False
                        elif c == 'h':
                            bytes_format = False
                            kilo_format = False
                            mega_format = False
                            giga_format = False
                            human_format = True
                        elif c == 't':
                            show_total = True
            i += 1
        
        # Get memory information
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        # Define divisor based on format
        if bytes_format:
            divisor = 1
            unit = "B"
        elif kilo_format:
            divisor = 1024
            unit = "K"
        elif mega_format:
            divisor = 1024 * 1024
            unit = "M"
        elif giga_format:
            divisor = 1024 * 1024 * 1024
            unit = "G"
        
        # Format output
        output = []
        
        # Add header
        output.append(f"{'':16s} {'total':>10s} {'used':>10s} {'free':>10s} {'shared':>10s} {'buff/cache':>10s} {'available':>10s}")
        
        # Add memory info
        if human_format:
            total = UnixSystemUtilities._format_size(mem.total)
            used = UnixSystemUtilities._format_size(mem.used)
            free = UnixSystemUtilities._format_size(mem.free)
            shared = UnixSystemUtilities._format_size(mem.shared)
            buffers = UnixSystemUtilities._format_size(mem.buffers + mem.cached)
            available = UnixSystemUtilities._format_size(mem.available)
        else:
            total = f"{mem.total / divisor:.1f}"
            used = f"{mem.used / divisor:.1f}"
            free = f"{mem.free / divisor:.1f}"
            shared = f"{getattr(mem, 'shared', 0) / divisor:.1f}"
            buffers = f"{(getattr(mem, 'buffers', 0) + getattr(mem, 'cached', 0)) / divisor:.1f}"
            available = f"{mem.available / divisor:.1f}"
        
        mem_line = f"Mem:{'':<12s} {total:>10s} {used:>10s} {free:>10s} {shared:>10s} {buffers:>10s} {available:>10s}"
        output.append(mem_line)
        
        # Add swap info
        if human_format:
            total = UnixSystemUtilities._format_size(swap.total)
            used = UnixSystemUtilities._format_size(swap.used)
            free = UnixSystemUtilities._format_size(swap.free)
        else:
            total = f"{swap.total / divisor:.1f}"
            used = f"{swap.used / divisor:.1f}"
            free = f"{swap.free / divisor:.1f}"
        
        swap_line = f"Swap:{'':<11s} {total:>10s} {used:>10s} {free:>10s}"
        output.append(swap_line)
        
        # Add total if requested
        if show_total:
            if human_format:
                total = UnixSystemUtilities._format_size(mem.total + swap.total)
                used = UnixSystemUtilities._format_size(mem.used + swap.used)
                free = UnixSystemUtilities._format_size(mem.free + swap.free)
            else:
                total = f"{(mem.total + swap.total) / divisor:.1f}"
                used = f"{(mem.used + swap.used) / divisor:.1f}"
                free = f"{(mem.free + swap.free) / divisor:.1f}"
            
            total_line = f"Total:{'':<10s} {total:>10s} {used:>10s} {free:>10s}"
            output.append(total_line)
        
        return "\n".join(output)
    
    @staticmethod
    def _format_size(size):
        """Format size in human-readable format"""
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size/1024:.1f}K"
        elif size < 1024 * 1024 * 1024:
            return f"{size/(1024*1024):.1f}M"
        else:
            return f"{size/(1024*1024*1024):.1f}G"
    
    @staticmethod
    def do_df(fs, cwd, arg):
        """
        Report file system disk space usage
        
        Usage: df [options] [file...]
        
        Options:
          -a, --all           Include dummy, duplicate, or inaccessible file systems
          -h, --human-readable  Print sizes in human readable format
          -k                   Use 1024-byte blocks (default)
          -m                   Use 1,048,576-byte blocks
          -T, --print-type     Print file system type
        """
        args = arg.split()
        
        # Parse options
        show_all = False
        human_readable = False
        use_k = True  # Default
        use_m = False
        print_type = False
        
        # Process arguments
        files = []
        
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                if args[i] in ['-a', '--all']:
                    show_all = True
                elif args[i] in ['-h', '--human-readable']:
                    human_readable = True
                elif args[i] == '-k':
                    use_k = True
                    use_m = False
                elif args[i] == '-m':
                    use_k = False
                    use_m = True
                elif args[i] in ['-T', '--print-type']:
                    print_type = True
                else:
                    # Process combined options
                    for c in args[i][1:]:
                        if c == 'a':
                            show_all = True
                        elif c == 'h':
                            human_readable = True
                        elif c == 'k':
                            use_k = True
                            use_m = False
                        elif c == 'm':
                            use_k = False
                            use_m = True
                        elif c == 'T':
                            print_type = True
            else:
                files.append(args[i])
            i += 1
        
        # Get disk usage
        try:
            if files:
                # Get disk usage for specified files/paths
                partitions = []
                for file_path in files:
                    # Resolve path
                    if not os.path.isabs(file_path):
                        path = os.path.join(cwd, file_path)
                    else:
                        path = file_path
                    
                    try:
                        # Get partition for the file/path
                        for part in psutil.disk_partitions(all=show_all):
                            if path.startswith(part.mountpoint):
                                partitions.append(part)
                                break
                    except Exception:
                        pass
            else:
                # Get all partitions
                partitions = psutil.disk_partitions(all=show_all)
            
            # Format output
            output = []
            
            # Add header
            if print_type:
                output.append(f"{'Filesystem':20s} {'Type':8s} {'Size':>10s} {'Used':>10s} {'Avail':>10s} {'Use%':>5s} {'Mounted on'}")
            else:
                output.append(f"{'Filesystem':20s} {'Size':>10s} {'Used':>10s} {'Avail':>10s} {'Use%':>5s} {'Mounted on'}")
            
            # Process each partition
            for part in partitions:
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    
                    # Define divisor based on format
                    if human_readable:
                        size = UnixSystemUtilities._format_size(usage.total)
                        used = UnixSystemUtilities._format_size(usage.used)
                        avail = UnixSystemUtilities._format_size(usage.free)
                    elif use_m:
                        divisor = 1024 * 1024
                        size = f"{usage.total / divisor:.0f}"
                        used = f"{usage.used / divisor:.0f}"
                        avail = f"{usage.free / divisor:.0f}"
                    else:  # use_k
                        divisor = 1024
                        size = f"{usage.total / divisor:.0f}"
                        used = f"{usage.used / divisor:.0f}"
                        avail = f"{usage.free / divisor:.0f}"
                    
                    # Calculate usage percentage
                    use_percent = f"{usage.percent:.0f}%"
                    
                    # Format line
                    if print_type:
                        output.append(f"{part.device:20s} {part.fstype:8s} {size:>10s} {used:>10s} {avail:>10s} {use_percent:>5s} {part.mountpoint}")
                    else:
                        output.append(f"{part.device:20s} {size:>10s} {used:>10s} {avail:>10s} {use_percent:>5s} {part.mountpoint}")
                except Exception:
                    if print_type:
                        output.append(f"{part.device:20s} {part.fstype:8s} {'':>10s} {'':>10s} {'':>10s} {'':>5s} {part.mountpoint}")
                    else:
                        output.append(f"{part.device:20s} {'':>10s} {'':>10s} {'':>10s} {'':>5s} {part.mountpoint}")
            
            return "\n".join(output)
        except Exception as e:
            return f"df: error: {str(e)}"
    
    @staticmethod
    def do_du(fs, cwd, arg):
        """
        Estimate file space usage
        
        Usage: du [options] [file...]
        
        Options:
          -a, --all           Write counts for all files, not just directories
          -h, --human-readable  Print sizes in human readable format
          -s, --summarize     Display only a total for each argument
          -c, --total         Produce a grand total
          -d, --max-depth=N   Print the total for a directory only if it is N or fewer levels below the command line argument
        """
        args = arg.split()
        
        # Parse options
        show_all = False
        human_readable = False
        summarize = False
        show_total = False
        max_depth = None
        
        # Process arguments
        paths = []
        
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                if args[i] in ['-a', '--all']:
                    show_all = True
                elif args[i] in ['-h', '--human-readable']:
                    human_readable = True
                elif args[i] in ['-s', '--summarize']:
                    summarize = True
                elif args[i] in ['-c', '--total']:
                    show_total = True
                elif args[i].startswith('-d=') or args[i].startswith('--max-depth='):
                    try:
                        max_depth = int(args[i].split('=')[1])
                    except ValueError:
                        return f"du: invalid max depth: '{args[i].split('=')[1]}'"
                elif args[i] == '-d' or args[i] == '--max-depth':
                    if i + 1 < len(args):
                        try:
                            max_depth = int(args[i+1])
                            i += 1
                        except ValueError:
                            return f"du: invalid max depth: '{args[i+1]}'"
                    else:
                        return "du: option requires an argument -- 'd'"
                else:
                    # Process combined options
                    for c in args[i][1:]:
                        if c == 'a':
                            show_all = True
                        elif c == 'h':
                            human_readable = True
                        elif c == 's':
                            summarize = True
                        elif c == 'c':
                            show_total = True
            else:
                paths.append(args[i])
            i += 1
        
        # If no paths specified, use current directory
        if not paths:
            paths = [cwd]
        
        # Calculate disk usage
        results = []
        grand_total = 0
        
        for path in paths:
            # Resolve path
            if not os.path.isabs(path):
                abs_path = os.path.join(cwd, path)
            else:
                abs_path = path
            
            try:
                # Check if path exists
                if not os.path.exists(abs_path):
                    results.append(f"du: cannot access '{path}': No such file or directory")
                    continue
                
                # Get disk usage for the path
                if os.path.isfile(abs_path):
                    # Single file
                    size = os.path.getsize(abs_path)
                    grand_total += size
                    
                    if human_readable:
                        size_str = UnixSystemUtilities._format_size(size)
                    else:
                        size_str = str(size // 1024)  # Size in KB
                    
                    results.append(f"{size_str:8s} {path}")
                else:
                    # Directory
                    if summarize:
                        # Get total size of directory
                        total_size = 0
                        for root, dirs, files in os.walk(abs_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                try:
                                    total_size += os.path.getsize(file_path)
                                except (FileNotFoundError, PermissionError):
                                    pass
                        
                        grand_total += total_size
                        
                        if human_readable:
                            size_str = UnixSystemUtilities._format_size(total_size)
                        else:
                            size_str = str(total_size // 1024)  # Size in KB
                        
                        results.append(f"{size_str:8s} {path}")
                    else:
                        # Walk directory and show all subdirectories (and files if show_all)
                        for root, dirs, files in os.walk(abs_path):
                            # Check depth
                            if max_depth is not None:
                                rel_path = os.path.relpath(root, abs_path)
                                depth = 0 if rel_path == '.' else rel_path.count(os.sep) + 1
                                if depth > max_depth:
                                    dirs[:] = []  # Don't descend any deeper
                                    continue
                            
                            # Calculate directory size
                            dir_size = 0
                            
                            # Add size of files in directory
                            for file in files:
                                file_path = os.path.join(root, file)
                                try:
                                    file_size = os.path.getsize(file_path)
                                    dir_size += file_size
                                    
                                    # Show file if show_all
                                    if show_all:
                                        rel_file_path = os.path.relpath(file_path, cwd)
                                        
                                        if human_readable:
                                            size_str = UnixSystemUtilities._format_size(file_size)
                                        else:
                                            size_str = str(file_size // 1024)  # Size in KB
                                        
                                        results.append(f"{size_str:8s} {rel_file_path}")
                                except (FileNotFoundError, PermissionError):
                                    pass
                            
                            # Show directory
                            rel_dir_path = os.path.relpath(root, cwd)
                            
                            if human_readable:
                                size_str = UnixSystemUtilities._format_size(dir_size)
                            else:
                                size_str = str(dir_size // 1024)  # Size in KB
                            
                            results.append(f"{size_str:8s} {rel_dir_path}")
                            
                            grand_total += dir_size
            except PermissionError:
                results.append(f"du: cannot read directory '{path}': Permission denied")
            except Exception as e:
                results.append(f"du: '{path}': {str(e)}")
        
        # Add grand total if requested
        if show_total:
            if human_readable:
                size_str = UnixSystemUtilities._format_size(grand_total)
            else:
                size_str = str(grand_total // 1024)  # Size in KB
            
            results.append(f"{size_str:8s} total")
        
        return "\n".join(results)

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("uname", UnixSystemUtilities.do_uname)
    shell.register_command("uptime", UnixSystemUtilities.do_uptime)
    shell.register_command("free", UnixSystemUtilities.do_free)
    shell.register_command("df", UnixSystemUtilities.do_df)
    shell.register_command("du", UnixSystemUtilities.do_du)

"""
Network Utilities for KOS Shell

This module implements Linux-style network commands for the KOS shell,
providing utilities for network diagnostics, monitoring, and information.
"""

import os
import re
import shlex
import logging
import socket
import subprocess
import time
import platform
import json
from typing import List, Dict, Any, Optional, Tuple, Union

logger = logging.getLogger('KOS.shell.net_utils')

class NetworkUtils:
    """Implementation of Linux-style network utilities for KOS shell."""
    
    @staticmethod
    def do_ping(fs, cwd, arg):
        """Send ICMP ECHO_REQUEST to network hosts
        
        Usage: ping [options] destination
        
        Options:
          -c count       Stop after sending count packets
          -i interval    Wait interval seconds between sending each packet
          -w timeout     Time to wait for a response, in seconds
          
        Examples:
          ping google.com
          ping -c 4 192.168.1.1
          ping -i 2 -w 10 example.com
        """
        args = shlex.split(arg)
        if not args:
            return NetworkUtils.do_ping.__doc__
        
        # Parse options
        count = None
        interval = 1.0
        timeout = 5.0
        destination = None
        
        i = 0
        while i < len(args):
            if args[i] == '-c' and i + 1 < len(args):
                try:
                    count = int(args[i + 1])
                    i += 2
                except ValueError:
                    return f"Invalid count: {args[i + 1]}"
            elif args[i] == '-i' and i + 1 < len(args):
                try:
                    interval = float(args[i + 1])
                    i += 2
                except ValueError:
                    return f"Invalid interval: {args[i + 1]}"
            elif args[i] == '-w' and i + 1 < len(args):
                try:
                    timeout = float(args[i + 1])
                    i += 2
                except ValueError:
                    return f"Invalid timeout: {args[i + 1]}"
            else:
                destination = args[i]
                i += 1
        
        if not destination:
            return "No destination specified"
        
        # Platform-specific ping command
        system = platform.system().lower()
        
        if system == 'windows':
            ping_cmd = ['ping']
            if count:
                ping_cmd.extend(['-n', str(count)])
            if timeout:
                ping_cmd.extend(['-w', str(int(timeout * 1000))])
            ping_cmd.append(destination)
        else:  # Unix-like
            ping_cmd = ['ping']
            if count:
                ping_cmd.extend(['-c', str(count)])
            if interval:
                ping_cmd.extend(['-i', str(interval)])
            if timeout:
                ping_cmd.extend(['-W', str(int(timeout))])
            ping_cmd.append(destination)
        
        try:
            # Execute ping command
            result = subprocess.run(ping_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if result.returncode == 0:
                return result.stdout
            else:
                return f"Ping failed:\n{result.stderr}\n{result.stdout}"
        except Exception as e:
            return f"Error executing ping: {str(e)}"
    
    @staticmethod
    def do_ifconfig(fs, cwd, arg):
        """Configure a network interface
        
        Usage: ifconfig [interface]
        
        If no interface is specified, all interfaces are displayed.
        
        Examples:
          ifconfig
          ifconfig eth0
        """
        args = shlex.split(arg)
        interface = args[0] if args else None
        
        # Get network interfaces
        try:
            import psutil
            
            if not hasattr(psutil, 'net_if_addrs'):
                return "Error: psutil module does not have network interface functionality"
            
            # Get interface addresses
            interfaces = psutil.net_if_addrs()
            
            # Filter by interface if specified
            if interface and interface not in interfaces:
                return f"Interface {interface} not found"
            
            if interface:
                interfaces = {interface: interfaces[interface]}
            
            # Get interface stats if available
            if hasattr(psutil, 'net_if_stats'):
                stats = psutil.net_if_stats()
            else:
                stats = {}
            
            # Format output
            result = []
            
            for name, addrs in interfaces.items():
                # Get interface status
                is_up = stats.get(name, None)
                status = "UP" if is_up and is_up.isup else "DOWN" if is_up else "UNKNOWN"
                
                # Start with interface name
                result.append(f"{name}: flags={status}")
                
                # Add addresses
                for addr in addrs:
                    addr_family = addr.family
                    
                    # Convert address family to string
                    if hasattr(socket, 'AF_INET') and addr_family == socket.AF_INET:
                        result.append(f"    inet {addr.address} netmask {addr.netmask}")
                    elif hasattr(socket, 'AF_INET6') and addr_family == socket.AF_INET6:
                        result.append(f"    inet6 {addr.address}")
                    elif hasattr(socket, 'AF_PACKET') and addr_family == socket.AF_PACKET:
                        result.append(f"    ether {addr.address}")
                
                # Add stats if available
                if name in stats:
                    speed = stats[name].speed
                    if speed > 0:
                        result.append(f"    speed {speed}Mb/s")
                
                # Add spacing between interfaces
                result.append("")
            
            return "\n".join(result)
        except ImportError:
            # Fallback to system ifconfig command
            try:
                if platform.system().lower() == 'windows':
                    return "ifconfig not available on Windows. Use 'ipconfig' instead."
                else:
                    cmd = ['ifconfig']
                    if interface:
                        cmd.append(interface)
                    
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    
                    if result.returncode == 0:
                        return result.stdout
                    else:
                        return f"ifconfig failed:\n{result.stderr}"
            except Exception as e:
                return f"Error executing ifconfig: {str(e)}"
    
    @staticmethod
    def do_netstat(fs, cwd, arg):
        """Print network connections, routing tables, interface statistics, etc.
        
        Usage: netstat [options]
        
        Options:
          -t, --tcp           Display TCP connections
          -u, --udp           Display UDP connections
          -l, --listening     Display only listening sockets
          -n, --numeric       Don't resolve hostnames
          -p, --programs      Show PID/Program name for sockets
          
        Examples:
          netstat
          netstat -t
          netstat -tulnp
        """
        args = shlex.split(arg)
        
        # Parse options
        show_tcp = False
        show_udp = False
        only_listening = False
        numeric = False
        show_programs = False
        
        # If no options, show everything
        if not args:
            show_tcp = True
            show_udp = True
        
        # Parse options
        for arg in args:
            if arg in ['-t', '--tcp']:
                show_tcp = True
            elif arg in ['-u', '--udp']:
                show_udp = True
            elif arg in ['-l', '--listening']:
                only_listening = True
            elif arg in ['-n', '--numeric']:
                numeric = True
            elif arg in ['-p', '--programs']:
                show_programs = True
            elif '-' in arg:
                # Handle combined options like -tulnp
                for char in arg[1:]:
                    if char == 't':
                        show_tcp = True
                    elif char == 'u':
                        show_udp = True
                    elif char == 'l':
                        only_listening = True
                    elif char == 'n':
                        numeric = True
                    elif char == 'p':
                        show_programs = True
        
        try:
            import psutil
            
            if not hasattr(psutil, 'net_connections'):
                return "Error: psutil module does not have network connection functionality"
            
            # Get network connections
            connections = psutil.net_connections()
            
            # Filter connections
            filtered_connections = []
            
            for conn in connections:
                # Filter by protocol
                if (conn.type == socket.SOCK_STREAM and show_tcp) or (conn.type == socket.SOCK_DGRAM and show_udp):
                    # Filter by state
                    if not only_listening or conn.status == 'LISTEN':
                        filtered_connections.append(conn)
            
            # Sort connections by protocol, local address, remote address
            filtered_connections.sort(key=lambda c: (c.type, c.laddr if c.laddr else "", c.raddr if c.raddr else ""))
            
            # Format header
            result = ["Proto  Local Address          Foreign Address        State       PID/Program"]
            
            # Format connections
            for conn in filtered_connections:
                # Determine protocol
                proto = "tcp" if conn.type == socket.SOCK_STREAM else "udp" if conn.type == socket.SOCK_DGRAM else "???"
                
                # Format local address
                if conn.laddr:
                    if numeric:
                        local_addr = f"{conn.laddr.ip}:{conn.laddr.port}"
                    else:
                        try:
                            local_host = socket.gethostbyaddr(conn.laddr.ip)[0] if not numeric else conn.laddr.ip
                        except (socket.herror, socket.gaierror):
                            local_host = conn.laddr.ip
                        local_addr = f"{local_host}:{conn.laddr.port}"
                else:
                    local_addr = "*:*"
                
                # Format remote address
                if conn.raddr:
                    if numeric:
                        remote_addr = f"{conn.raddr.ip}:{conn.raddr.port}"
                    else:
                        try:
                            remote_host = socket.gethostbyaddr(conn.raddr.ip)[0] if not numeric else conn.raddr.ip
                        except (socket.herror, socket.gaierror):
                            remote_host = conn.raddr.ip
                        remote_addr = f"{remote_host}:{conn.raddr.port}"
                else:
                    remote_addr = "*:*"
                
                # Format state
                state = conn.status if conn.status else "ESTABLISHED"
                
                # Format program info
                if show_programs and conn.pid:
                    try:
                        proc = psutil.Process(conn.pid)
                        prog_info = f"{conn.pid}/{proc.name()}"
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        prog_info = f"{conn.pid}/-"
                else:
                    prog_info = "-"
                
                # Add to result
                result.append(f"{proto:<6} {local_addr:<22} {remote_addr:<22} {state:<11} {prog_info}")
            
            return "\n".join(result)
        except ImportError:
            # Fallback to system netstat command
            try:
                cmd = ['netstat']
                
                if platform.system().lower() == 'windows':
                    if show_tcp:
                        cmd.append('-t')
                    if show_udp:
                        cmd.append('-u')
                    if only_listening:
                        cmd.append('-a')
                    if numeric:
                        cmd.append('-n')
                else:  # Unix-like
                    options = ''
                    if show_tcp:
                        options += 't'
                    if show_udp:
                        options += 'u'
                    if only_listening:
                        options += 'l'
                    if numeric:
                        options += 'n'
                    if show_programs:
                        options += 'p'
                    
                    if options:
                        cmd.append(f'-{options}')
                
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                if result.returncode == 0:
                    return result.stdout
                else:
                    return f"netstat failed:\n{result.stderr}"
            except Exception as e:
                return f"Error executing netstat: {str(e)}"
    
    @staticmethod
    def do_curl(fs, cwd, arg):
        """Transfer data from or to a server
        
        Usage: curl [options] URL
        
        Options:
          -o, --output FILE   Write to FILE instead of stdout
          -I, --head          Show document info only
          -s, --silent        Silent mode
          -v, --verbose       Make the operation more talkative
          
        Examples:
          curl https://example.com
          curl -o output.html https://example.com
          curl -I https://example.com
        """
        args = shlex.split(arg)
        if not args:
            return NetworkUtils.do_curl.__doc__
        
        # Parse options
        output_file = None
        head_only = False
        silent = False
        verbose = False
        url = None
        
        i = 0
        while i < len(args):
            if args[i] in ['-o', '--output'] and i + 1 < len(args):
                output_file = args[i + 1]
                i += 2
            elif args[i] in ['-I', '--head']:
                head_only = True
                i += 1
            elif args[i] in ['-s', '--silent']:
                silent = True
                i += 1
            elif args[i] in ['-v', '--verbose']:
                verbose = True
                i += 1
            else:
                url = args[i]
                i += 1
        
        if not url:
            return "No URL specified"
        
        try:
            import requests
            
            headers = {}
            if head_only:
                response = requests.head(url)
            else:
                response = requests.get(url)
            
            if not silent and verbose:
                result = [f"* Connected to {urlparse(url).netloc}"]
                result.append(f"> {response.request.method} {url}")
                for name, value in response.request.headers.items():
                    result.append(f"> {name}: {value}")
                result.append(">")
                result.append(f"< HTTP/1.1 {response.status_code} {response.reason}")
                for name, value in response.headers.items():
                    result.append(f"< {name}: {value}")
                result.append("<")
                
                if not head_only:
                    if output_file:
                        with open(os.path.join(cwd, output_file), 'wb') as f:
                            f.write(response.content)
                        result.append(f"* Saved to {output_file}")
                    else:
                        result.append(response.text)
                
                return "\n".join(result)
            else:
                if head_only:
                    result = [f"HTTP/1.1 {response.status_code} {response.reason}"]
                    for name, value in response.headers.items():
                        result.append(f"{name}: {value}")
                    return "\n".join(result)
                else:
                    if output_file:
                        with open(os.path.join(cwd, output_file), 'wb') as f:
                            f.write(response.content)
                        if not silent:
                            return f"Downloaded {len(response.content)} bytes to {output_file}"
                        else:
                            return ""
                    else:
                        return response.text
        except ImportError:
            try:
                import urllib.request
                import urllib.error
                from urllib.parse import urlparse
                
                if verbose:
                    result = [f"* Connected to {urlparse(url).netloc}"]
                
                if head_only:
                    req = urllib.request.Request(url, method='HEAD')
                else:
                    req = urllib.request.Request(url)
                
                try:
                    with urllib.request.urlopen(req) as response:
                        if head_only:
                            result = [f"HTTP/1.1 {response.code} {response.reason}"]
                            for name, value in response.headers.items():
                                result.append(f"{name}: {value}")
                            return "\n".join(result)
                        else:
                            content = response.read()
                            if output_file:
                                with open(os.path.join(cwd, output_file), 'wb') as f:
                                    f.write(content)
                                if not silent:
                                    return f"Downloaded {len(content)} bytes to {output_file}"
                                else:
                                    return ""
                            else:
                                return content.decode('utf-8', errors='replace')
                except urllib.error.HTTPError as e:
                    return f"HTTP Error {e.code}: {e.reason}"
                except urllib.error.URLError as e:
                    return f"URL Error: {e.reason}"
            except ImportError:
                # Fallback to system curl command
                try:
                    cmd = ['curl']
                    
                    if output_file:
                        cmd.extend(['-o', output_file])
                    if head_only:
                        cmd.append('-I')
                    if silent:
                        cmd.append('-s')
                    if verbose:
                        cmd.append('-v')
                    
                    cmd.append(url)
                    
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    
                    if result.returncode == 0:
                        return result.stdout
                    else:
                        return f"curl failed:\n{result.stderr}"
                except Exception as e:
                    return f"Error executing curl: {str(e)}"
    
    @staticmethod
    def do_wget(fs, cwd, arg):
        """Non-interactive network downloader
        
        Usage: wget [options] URL
        
        Options:
          -O, --output-document=FILE    Write documents to FILE
          -q, --quiet                   Quiet (no output)
          -v, --verbose                 Be verbose
          
        Examples:
          wget https://example.com/file.txt
          wget -O output.txt https://example.com/file.txt
          wget -q https://example.com/file.txt
        """
        args = shlex.split(arg)
        if not args:
            return NetworkUtils.do_wget.__doc__
        
        # Parse options
        output_file = None
        quiet = False
        verbose = False
        url = None
        
        i = 0
        while i < len(args):
            if args[i] in ['-O', '--output-document'] and i + 1 < len(args):
                output_file = args[i + 1]
                i += 2
            elif args[i].startswith('--output-document='):
                output_file = args[i][17:]
                i += 1
            elif args[i] in ['-q', '--quiet']:
                quiet = True
                i += 1
            elif args[i] in ['-v', '--verbose']:
                verbose = True
                i += 1
            else:
                url = args[i]
                i += 1
        
        if not url:
            return "No URL specified"
        
        try:
            import requests
            from urllib.parse import urlparse
            
            if not quiet and verbose:
                print(f"--{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}--  {url}")
                print(f"Resolving {urlparse(url).netloc}...")
                print(f"Connecting to {urlparse(url).netloc}...")
            
            response = requests.get(url, stream=True)
            
            if not response.ok:
                return f"HTTP Error {response.status_code}: {response.reason}"
            
            # Determine output filename if not specified
            if not output_file:
                parsed_url = urlparse(url)
                output_file = os.path.basename(parsed_url.path)
                if not output_file:
                    output_file = 'index.html'
            
            # Get file size
            file_size = int(response.headers.get('content-length', 0))
            
            if not quiet:
                if file_size > 0:
                    print(f"Length: {file_size} ({file_size/1024/1024:.1f}M)")
                else:
                    print("Length: unknown")
                print(f"Saving to: '{output_file}'")
            
            # Download the file
            full_path = os.path.join(cwd, output_file)
            downloaded = 0
            
            with open(full_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if not quiet and verbose and file_size > 0:
                            percent = int(downloaded * 100 / file_size)
                            bar_length = 20
                            bar = '=' * int(bar_length * percent / 100)
                            if bar:
                                bar = bar[:-1] + '>'
                            spaces = ' ' * (bar_length - len(bar))
                            print(f"\r{percent}% [{bar}{spaces}] {downloaded}/{file_size}", end='')
            
            if not quiet:
                if verbose:
                    print("\nDownload complete")
                
                elapsed = response.elapsed.total_seconds()
                if elapsed > 0:
                    speed = downloaded / elapsed / 1024  # KB/s
                    print(f"{output_file} saved [{downloaded} bytes in {elapsed:.1f}s ({speed:.1f}KB/s)]")
            
            return "" if quiet else f"Successfully downloaded {url} to {output_file}"
        except ImportError:
            try:
                import urllib.request
                import urllib.error
                from urllib.parse import urlparse
                
                try:
                    if not quiet and verbose:
                        print(f"--{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}--  {url}")
                        print(f"Resolving {urlparse(url).netloc}...")
                        print(f"Connecting to {urlparse(url).netloc}...")
                    
                    with urllib.request.urlopen(url) as response:
                        # Determine output filename if not specified
                        if not output_file:
                            parsed_url = urlparse(url)
                            output_file = os.path.basename(parsed_url.path)
                            if not output_file:
                                output_file = 'index.html'
                        
                        # Get file size
                        file_size = int(response.headers.get('Content-Length', 0))
                        
                        if not quiet:
                            if file_size > 0:
                                print(f"Length: {file_size} ({file_size/1024/1024:.1f}M)")
                            else:
                                print("Length: unknown")
                            print(f"Saving to: '{output_file}'")
                        
                        # Download the file
                        full_path = os.path.join(cwd, output_file)
                        downloaded = 0
                        
                        with open(full_path, 'wb') as f:
                            start_time = time.time()
                            while True:
                                chunk = response.read(8192)
                                if not chunk:
                                    break
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                if not quiet and verbose and file_size > 0:
                                    percent = int(downloaded * 100 / file_size)
                                    bar_length = 20
                                    bar = '=' * int(bar_length * percent / 100)
                                    if bar:
                                        bar = bar[:-1] + '>'
                                    spaces = ' ' * (bar_length - len(bar))
                                    print(f"\r{percent}% [{bar}{spaces}] {downloaded}/{file_size}", end='')
                        
                        if not quiet:
                            if verbose:
                                print("\nDownload complete")
                            
                            elapsed = time.time() - start_time
                            if elapsed > 0:
                                speed = downloaded / elapsed / 1024  # KB/s
                                print(f"{output_file} saved [{downloaded} bytes in {elapsed:.1f}s ({speed:.1f}KB/s)]")
                        
                        return "" if quiet else f"Successfully downloaded {url} to {output_file}"
                except urllib.error.HTTPError as e:
                    return f"HTTP Error {e.code}: {e.reason}"
                except urllib.error.URLError as e:
                    return f"URL Error: {e.reason}"
            except ImportError:
                # Fallback to system wget command
                try:
                    cmd = ['wget']
                    
                    if output_file:
                        cmd.extend(['-O', output_file])
                    if quiet:
                        cmd.append('-q')
                    if verbose:
                        cmd.append('-v')
                    
                    cmd.append(url)
                    
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    
                    if result.returncode == 0:
                        return result.stdout or "Download successful"
                    else:
                        return f"wget failed:\n{result.stderr}"
                except Exception as e:
                    return f"Error executing wget: {str(e)}"

def register_commands(shell):
    """Register all network utility commands with the KOS shell."""
    
    # Register the ping command
    def do_ping(self, arg):
        """Send ICMP ECHO_REQUEST to network hosts"""
        try:
            result = NetworkUtils.do_ping(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in ping command: {e}")
            print(f"ping: {str(e)}")
    
    # Register the ifconfig command
    def do_ifconfig(self, arg):
        """Configure a network interface"""
        try:
            result = NetworkUtils.do_ifconfig(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in ifconfig command: {e}")
            print(f"ifconfig: {str(e)}")
    
    # Register the netstat command
    def do_netstat(self, arg):
        """Print network connections, routing tables, interface statistics"""
        try:
            result = NetworkUtils.do_netstat(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in netstat command: {e}")
            print(f"netstat: {str(e)}")
    
    # Register the curl command
    def do_curl(self, arg):
        """Transfer data from or to a server"""
        try:
            result = NetworkUtils.do_curl(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in curl command: {e}")
            print(f"curl: {str(e)}")
    
    # Register the wget command
    def do_wget(self, arg):
        """Non-interactive network downloader"""
        try:
            result = NetworkUtils.do_wget(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in wget command: {e}")
            print(f"wget: {str(e)}")
    
    # Attach the command methods to the shell
    setattr(shell.__class__, 'do_ping', do_ping)
    setattr(shell.__class__, 'do_ifconfig', do_ifconfig)
    setattr(shell.__class__, 'do_netstat', do_netstat)
    setattr(shell.__class__, 'do_curl', do_curl)
    setattr(shell.__class__, 'do_wget', do_wget)

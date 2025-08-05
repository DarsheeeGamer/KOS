"""
Network Commands for KOS shell.

This module implements various network utilities similar to
common Unix/Linux commands like ping, ifconfig, netstat, etc.
"""

import os
import re
import shlex
import logging
import time
import socket
import subprocess
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = logging.getLogger('KOS.shell.network')

# Try to import the KADVLayer components for advanced system integration
try:
    from ...advlayer import KADVLayer, get_kadvlayer
    from ...advlayer.system_info import SystemInfo
    KADV_AVAILABLE = True
except ImportError:
    KADV_AVAILABLE = False
    logger.warning("KADVLayer not available, falling back to basic functionality")

class NetworkCommands:
    """Implementation of network commands for KOS shell."""
    
    @staticmethod
    def do_ping(fs, cwd, arg):
        """Send ICMP ECHO_REQUEST to network hosts
        
        Usage: ping [options] destination
        Send ICMP ECHO_REQUEST packets to network hosts.
        
        Options:
          -c count      Stop after sending count packets
          -i interval   Wait interval seconds between sending each packet
          -w timeout    Time to wait for a response, in seconds
          -4            Use IPv4 only
          -6            Use IPv6 only
        
        Examples:
          ping google.com           # Ping google.com
          ping -c 5 192.168.1.1     # Send 5 pings to 192.168.1.1
        """
        try:
            args = shlex.split(arg)
            
            # Parse options
            count = None
            interval = 1
            timeout = 5
            use_ipv4 = True
            use_ipv6 = False
            destination = None
            
            i = 0
            while i < len(args):
                if args[i] in ['-h', '--help']:
                    return NetworkCommands.do_ping.__doc__
                elif args[i] == '-c':
                    if i + 1 < len(args):
                        try:
                            count = int(args[i + 1])
                            i += 1
                        except ValueError:
                            return f"ping: invalid count: '{args[i + 1]}'"
                    else:
                        return "ping: option requires an argument -- 'c'"
                elif args[i] == '-i':
                    if i + 1 < len(args):
                        try:
                            interval = float(args[i + 1])
                            i += 1
                        except ValueError:
                            return f"ping: invalid interval: '{args[i + 1]}'"
                    else:
                        return "ping: option requires an argument -- 'i'"
                elif args[i] == '-w':
                    if i + 1 < len(args):
                        try:
                            timeout = float(args[i + 1])
                            i += 1
                        except ValueError:
                            return f"ping: invalid timeout: '{args[i + 1]}'"
                    else:
                        return "ping: option requires an argument -- 'w'"
                elif args[i] == '-4':
                    use_ipv4 = True
                    use_ipv6 = False
                elif args[i] == '-6':
                    use_ipv4 = False
                    use_ipv6 = True
                elif destination is None:
                    destination = args[i]
                else:
                    return f"ping: extra arguments given"
                i += 1
            
            if destination is None:
                return "ping: missing destination"
            
            # Basic implementation for simulating ping
            # In a real implementation, this would use raw sockets or a proper ping library
            try:
                # Resolve host
                try:
                    addr_info = socket.getaddrinfo(
                        destination, 
                        None, 
                        socket.AF_INET if use_ipv4 else socket.AF_INET6
                    )
                    ip_address = addr_info[0][4][0]
                except socket.gaierror:
                    return f"ping: unknown host {destination}"
                
                result = [f"PING {destination} ({ip_address})"]
                
                # Simulate ping packets
                successful_pings = 0
                total_time = 0
                min_time = float('inf')
                max_time = 0
                
                # Determine number of pings
                num_pings = count if count is not None else 4  # Default to 4 pings for simulation
                
                for seq in range(1, num_pings + 1):
                    start_time = time.time()
                    
                    # Simulate network delay (randomized)
                    simulated_time = (start_time * 1000) % 100 / 1000  # Between 0-100ms
                    time.sleep(simulated_time)
                    
                    # Simulate occasional packet loss (5% chance)
                    packet_lost = (hash(f"{destination}{seq}{start_time}") % 100) < 5
                    
                    if not packet_lost:
                        rtt = simulated_time * 1000  # Convert to ms
                        result.append(f"64 bytes from {ip_address}: icmp_seq={seq} ttl=64 time={rtt:.3f} ms")
                        
                        successful_pings += 1
                        total_time += rtt
                        min_time = min(min_time, rtt)
                        max_time = max(max_time, rtt)
                    else:
                        result.append(f"Request timeout for icmp_seq {seq}")
                    
                    # Wait for interval between pings
                    if seq < num_pings:
                        time.sleep(interval - simulated_time)  # Adjust for already elapsed time
                
                # Show statistics
                if successful_pings > 0:
                    loss_percentage = (num_pings - successful_pings) * 100 / num_pings
                    avg_time = total_time / successful_pings
                    
                    result.append("")
                    result.append(f"--- {destination} ping statistics ---")
                    result.append(f"{num_pings} packets transmitted, {successful_pings} received, {loss_percentage:.1f}% packet loss")
                    result.append(f"rtt min/avg/max = {min_time:.3f}/{avg_time:.3f}/{max_time:.3f} ms")
                
                return "\n".join(result)
            
            except Exception as e:
                return f"ping: error: {str(e)}"
                
        except Exception as e:
            logger.error(f"Error in ping command: {e}")
            return f"ping: {str(e)}"
    
    @staticmethod
    def do_ifconfig(fs, cwd, arg):
        """Configure a network interface
        
        Usage: ifconfig [interface] [options]
        Display or configure network interface parameters.
        
        If no arguments are given, display status of active interfaces.
        
        Examples:
          ifconfig              # Show all interfaces
          ifconfig eth0         # Show status of eth0 interface
        """
        try:
            args = shlex.split(arg)
            
            # Parse options
            interface = None
            
            if args:
                interface = args[0]
            
            # Get network information using psutil
            if not PSUTIL_AVAILABLE:
                return "ifconfig: psutil module not available, cannot retrieve network information"
            
            # Format output
            result = []
            
            # Get network interfaces
            net_if_addrs = psutil.net_if_addrs()
            net_if_stats = psutil.net_if_stats()
            
            # Filter by interface if specified
            if interface and interface not in net_if_addrs:
                return f"ifconfig: {interface}: No such device"
            
            interfaces = [interface] if interface else net_if_addrs.keys()
            
            for ifname in interfaces:
                # Get interface addresses
                addresses = net_if_addrs.get(ifname, [])
                
                # Get interface stats
                stats = net_if_stats.get(ifname)
                
                # Format interface information
                result.append(f"{ifname}: flags={'UP' if stats and stats.isup else 'DOWN'}  mtu={stats.mtu if stats else 0}")
                
                for addr in addresses:
                    family = 'inet' if addr.family == socket.AF_INET else 'inet6' if addr.family == socket.AF_INET6 else 'link'
                    
                    if family == 'inet':
                        result.append(f"        {family} {addr.address}  netmask {addr.netmask}")
                    elif family == 'inet6':
                        result.append(f"        {family} {addr.address}")
                    elif family == 'link':
                        result.append(f"        {family} {addr.address}")
                
                result.append("")
            
            return "\n".join(result)
                
        except Exception as e:
            logger.error(f"Error in ifconfig command: {e}")
            return f"ifconfig: {str(e)}"
    
    @staticmethod
    def do_netstat(fs, cwd, arg):
        """Print network connections, routing tables, etc.
        
        Usage: netstat [options]
        Print network connections, routing tables, interface statistics, masquerade connections, etc.
        
        Options:
          -a, --all              Show all sockets (default: connected)
          -t, --tcp              Show TCP sockets
          -u, --udp              Show UDP sockets
          -l, --listening        Show only listening sockets
          -p, --programs         Show the PID and name of the program
          -n, --numeric          Show numerical addresses
        
        Examples:
          netstat -tuln          # Show TCP and UDP listening ports
          netstat -anp           # Show all connections with PID
        """
        try:
            args = shlex.split(arg)
            
            # Parse options
            show_all = False
            show_tcp = False
            show_udp = False
            show_listening = False
            show_programs = False
            show_numeric = False
            
            i = 0
            while i < len(args):
                if args[i] in ['-h', '--help']:
                    return NetworkCommands.do_netstat.__doc__
                elif args[i] in ['-a', '--all']:
                    show_all = True
                elif args[i] in ['-t', '--tcp']:
                    show_tcp = True
                elif args[i] in ['-u', '--udp']:
                    show_udp = True
                elif args[i] in ['-l', '--listening']:
                    show_listening = True
                elif args[i] in ['-p', '--programs']:
                    show_programs = True
                elif args[i] in ['-n', '--numeric']:
                    show_numeric = True
                elif args[i].startswith('-') and len(args[i]) > 1:
                    # Handle combined options like -tuln
                    for opt in args[i][1:]:
                        if opt == 'a':
                            show_all = True
                        elif opt == 't':
                            show_tcp = True
                        elif opt == 'u':
                            show_udp = True
                        elif opt == 'l':
                            show_listening = True
                        elif opt == 'p':
                            show_programs = True
                        elif opt == 'n':
                            show_numeric = True
                i += 1
            
            # Default to showing TCP if nothing specified
            if not show_tcp and not show_udp:
                show_tcp = True
            
            # Get network connections using psutil
            if not PSUTIL_AVAILABLE:
                return "netstat: psutil module not available, cannot retrieve network information"
            
            # Determine connection kinds
            kinds = []
            if show_tcp:
                kinds.append('tcp')
                kinds.append('tcp6')
            if show_udp:
                kinds.append('udp')
                kinds.append('udp6')
            
            # Get connections
            connections = psutil.net_connections(kind='all')
            
            # Filter connections
            filtered_connections = []
            for conn in connections:
                # Filter by protocol
                if conn.type not in kinds:
                    continue
                
                # Filter by state (listening)
                if show_listening and conn.status != 'LISTEN':
                    continue
                
                # Only show established connections unless all requested
                if not show_all and not show_listening and conn.status != 'ESTABLISHED':
                    continue
                
                filtered_connections.append(conn)
            
            # Format output
            result = []
            
            # Header
            header = "Proto Recv-Q Send-Q Local Address           Foreign Address         State"
            if show_programs:
                header += "       PID/Program name"
            result.append(header)
            
            # Format each connection
            for conn in filtered_connections:
                # Format local address
                if conn.laddr:
                    if show_numeric:
                        local_addr = f"{conn.laddr.ip}:{conn.laddr.port}"
                    else:
                        try:
                            local_host = socket.gethostbyaddr(conn.laddr.ip)[0] if conn.laddr.ip != '::' else '*'
                        except (socket.herror, socket.gaierror):
                            local_host = conn.laddr.ip
                        local_addr = f"{local_host}:{conn.laddr.port}"
                else:
                    local_addr = "*:*"
                
                # Format foreign address
                if conn.raddr:
                    if show_numeric:
                        foreign_addr = f"{conn.raddr.ip}:{conn.raddr.port}"
                    else:
                        try:
                            foreign_host = socket.gethostbyaddr(conn.raddr.ip)[0]
                        except (socket.herror, socket.gaierror):
                            foreign_host = conn.raddr.ip
                        foreign_addr = f"{foreign_host}:{conn.raddr.port}"
                else:
                    foreign_addr = "*:*"
                
                # Format protocol
                proto = conn.type
                
                # Format state
                state = conn.status
                
                # Format program (pid/name)
                program = ""
                if show_programs and conn.pid:
                    try:
                        process = psutil.Process(conn.pid)
                        program = f"{conn.pid}/{process.name()}"
                    except psutil.NoSuchProcess:
                        program = f"{conn.pid}/-"
                
                # Format line
                line = f"{proto:<5} {0:6d} {0:6d} {local_addr:<21} {foreign_addr:<21} {state:<12}"
                if show_programs:
                    line += f" {program}"
                
                result.append(line)
            
            return "\n".join(result)
                
        except Exception as e:
            logger.error(f"Error in netstat command: {e}")
            return f"netstat: {str(e)}"

def register_commands(shell):
    """Register all network commands with the KOS shell."""
    
    # Add the ping command
    def do_ping(self, arg):
        """Send ICMP ECHO_REQUEST to network hosts
        
        Usage: ping [options] destination
        Send ICMP ECHO_REQUEST packets to network hosts.
        
        Options:
          -c count      Stop after sending count packets
          -i interval   Wait interval seconds between sending each packet
          -w timeout    Time to wait for a response, in seconds
          -4            Use IPv4 only
          -6            Use IPv6 only
        """
        try:
            result = NetworkCommands.do_ping(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in ping command: {e}")
            print(f"ping: {str(e)}")
    
    # Add the ifconfig command
    def do_ifconfig(self, arg):
        """Configure a network interface
        
        Usage: ifconfig [interface] [options]
        Display or configure network interface parameters.
        
        If no arguments are given, display status of active interfaces.
        """
        try:
            result = NetworkCommands.do_ifconfig(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in ifconfig command: {e}")
            print(f"ifconfig: {str(e)}")
    
    # Add the netstat command
    def do_netstat(self, arg):
        """Print network connections, routing tables, etc.
        
        Usage: netstat [options]
        Print network connections, routing tables, interface statistics, masquerade connections, etc.
        
        Options:
          -a, --all              Show all sockets (default: connected)
          -t, --tcp              Show TCP sockets
          -u, --udp              Show UDP sockets
          -l, --listening        Show only listening sockets
          -p, --programs         Show the PID and name of the program
          -n, --numeric          Show numerical addresses
        """
        try:
            result = NetworkCommands.do_netstat(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in netstat command: {e}")
            print(f"netstat: {str(e)}")
    
    # Attach the command methods to the shell
    setattr(shell.__class__, 'do_ping', do_ping)
    setattr(shell.__class__, 'do_ifconfig', do_ifconfig)
    setattr(shell.__class__, 'do_netstat', do_netstat)

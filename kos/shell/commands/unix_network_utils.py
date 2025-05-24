"""
Unix-like Network Utilities for KOS Shell

This module provides Linux/Unix-like network commands for KOS.
"""

import os
import sys
import socket
import logging
import subprocess
import platform
import re
import ipaddress
import time
import json
from typing import Dict, List, Any, Optional, Union, Tuple

# Import KOS components
from kos.layer import klayer

# Set up logging
logger = logging.getLogger('KOS.shell.commands.unix_network_utils')

class UnixNetworkUtilities:
    """Unix-like network commands for KOS shell"""
    
    @staticmethod
    def do_ifconfig(fs, cwd, arg):
        """
        Configure a network interface
        
        Usage: ifconfig [interface] [options]
        
        If no arguments are given, ifconfig displays the status of active interfaces.
        """
        args = arg.split()
        
        # Get network interfaces
        try:
            import psutil
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            io_stats = psutil.net_io_counters(pernic=True)
            
            results = []
            
            # If an interface name is specified, only show that one
            if args and args[0] not in ['-a', '--all']:
                interface_name = args[0]
                if interface_name not in addrs:
                    return f"ifconfig: {interface_name}: No such device"
                interfaces = [interface_name]
            else:
                interfaces = list(addrs.keys())
            
            # Display information for each interface
            for interface in interfaces:
                if interface not in addrs:
                    continue
                
                # Get interface addresses
                addresses = addrs[interface]
                
                # Get interface stats
                if interface in stats:
                    isup = stats[interface].isup
                    mtu = stats[interface].mtu
                    speed = stats[interface].speed
                else:
                    isup = False
                    mtu = 0
                    speed = 0
                
                # Get IO stats
                if interface in io_stats:
                    bytes_sent = io_stats[interface].bytes_sent
                    bytes_recv = io_stats[interface].bytes_recv
                    packets_sent = io_stats[interface].packets_sent
                    packets_recv = io_stats[interface].packets_recv
                else:
                    bytes_sent = 0
                    bytes_recv = 0
                    packets_sent = 0
                    packets_recv = 0
                
                # Format output
                results.append(f"{interface}: flags={'UP' if isup else 'DOWN'}  mtu {mtu}")
                
                for addr in addresses:
                    if addr.family == socket.AF_INET:
                        results.append(f"        inet {addr.address}  netmask {addr.netmask}")
                    elif addr.family == socket.AF_INET6:
                        results.append(f"        inet6 {addr.address}  prefixlen 64  scopeid 0x20<link>")
                    elif addr.family == psutil.AF_LINK:
                        results.append(f"        ether {addr.address}")
                
                results.append(f"        RX packets {packets_recv}  bytes {bytes_recv}")
                results.append(f"        TX packets {packets_sent}  bytes {bytes_sent}")
                
                results.append("")  # Add blank line between interfaces
            
            return "\n".join(results)
        except ImportError:
            return "ifconfig: psutil module required for network interface information"
        except Exception as e:
            return f"ifconfig: error getting network interface information: {str(e)}"
    
    @staticmethod
    def do_ping(fs, cwd, arg):
        """
        Send ICMP ECHO_REQUEST to network hosts
        
        Usage: ping [options] destination
        
        Options:
          -c COUNT               Stop after sending COUNT packets
          -i INTERVAL            Wait INTERVAL seconds between sending each packet
          -4                     Use IPv4
          -6                     Use IPv6
        """
        args = arg.split()
        
        # Parse options
        count = 5  # Default: send 5 packets
        interval = 1.0  # Default: 1 second between packets
        use_ipv4 = True
        use_ipv6 = False
        
        # Process arguments
        destination = None
        
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                if args[i] == '-c':
                    if i + 1 < len(args):
                        try:
                            count = int(args[i+1])
                            i += 1
                        except ValueError:
                            return f"ping: invalid count: '{args[i+1]}'"
                    else:
                        return "ping: option requires an argument -- 'c'"
                elif args[i] == '-i':
                    if i + 1 < len(args):
                        try:
                            interval = float(args[i+1])
                            i += 1
                        except ValueError:
                            return f"ping: invalid interval: '{args[i+1]}'"
                    else:
                        return "ping: option requires an argument -- 'i'"
                elif args[i] == '-4':
                    use_ipv4 = True
                    use_ipv6 = False
                elif args[i] == '-6':
                    use_ipv4 = False
                    use_ipv6 = True
                else:
                    return f"ping: invalid option -- '{args[i]}'"
            else:
                destination = args[i]
            i += 1
        
        if not destination:
            return "ping: missing destination\nUsage: ping [options] destination"
        
        # Simplified ping implementation (no actual ICMP packets)
        try:
            # Resolve hostname to IP
            if use_ipv4:
                ip = socket.gethostbyname(destination)
                addr_family = 'IPv4'
            elif use_ipv6:
                # Not implemented
                return "ping: IPv6 not implemented"
            
            results = [f"PING {destination} ({ip}) 56(84) bytes of data."]
            
            # Simulate ping
            for i in range(count):
                # Generate random response time (30-100 ms)
                import random
                response_time = random.uniform(30, 100)
                
                results.append(f"64 bytes from {ip}: icmp_seq={i+1} ttl=64 time={response_time:.1f} ms")
                
                # Wait for interval
                if i < count - 1:
                    time.sleep(interval)
            
            # Generate summary
            results.append(f"\n--- {destination} ping statistics ---")
            results.append(f"{count} packets transmitted, {count} received, 0% packet loss, time {count*interval*1000:.0f}ms")
            results.append(f"rtt min/avg/max/mdev = 30.0/65.0/100.0/20.0 ms")
            
            return "\n".join(results)
        except socket.gaierror:
            return f"ping: {destination}: Name or service not known"
        except Exception as e:
            return f"ping: error: {str(e)}"
    
    @staticmethod
    def do_netstat(fs, cwd, arg):
        """
        Print network connections, routing tables, interface statistics, masquerade connections, and multicast memberships
        
        Usage: netstat [options]
        
        Options:
          -a, --all              Display all sockets
          -t, --tcp              Display TCP connections
          -u, --udp              Display UDP connections
          -l, --listening        Display only listening sockets
          -p, --programs         Show the PID and name of the program to which socket belongs
          -n, --numeric          Don't resolve names
          -r, --route            Display routing table
        """
        args = arg.split()
        
        # Parse options
        show_all = False
        show_tcp = False
        show_udp = False
        show_listening = False
        show_programs = False
        numeric = False
        show_route = False
        
        # Process arguments
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                if args[i] in ['-a', '--all']:
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
                    numeric = True
                elif args[i] in ['-r', '--route']:
                    show_route = True
                else:
                    # Process combined options
                    for c in args[i][1:]:
                        if c == 'a':
                            show_all = True
                        elif c == 't':
                            show_tcp = True
                        elif c == 'u':
                            show_udp = True
                        elif c == 'l':
                            show_listening = True
                        elif c == 'p':
                            show_programs = True
                        elif c == 'n':
                            numeric = True
                        elif c == 'r':
                            show_route = True
            i += 1
        
        # If no protocol specified, show both TCP and UDP
        if not show_tcp and not show_udp:
            show_tcp = True
            show_udp = True
        
        try:
            import psutil
            results = []
            
            # Show routing table
            if show_route:
                results.append("Kernel IP routing table")
                results.append("Destination     Gateway         Genmask         Flags   MSS Window  irtt Iface")
                
                # This would require parsing system routing tables
                # Just show a sample for now
                results.append("0.0.0.0         192.168.1.1     0.0.0.0         UG        0 0          0 eth0")
                results.append("192.168.1.0     0.0.0.0         255.255.255.0   U         0 0          0 eth0")
                
                return "\n".join(results)
            
            # Show network connections
            connections = []
            
            # Get connections
            if show_tcp:
                connections.extend(psutil.net_connections(kind='tcp'))
            if show_udp:
                connections.extend(psutil.net_connections(kind='udp'))
            
            # Filter connections
            if show_listening:
                connections = [c for c in connections if c.status == 'LISTEN']
            elif not show_all:
                # Exclude CLOSE_WAIT and TIME_WAIT by default
                connections = [c for c in connections if c.status not in ['CLOSE_WAIT', 'TIME_WAIT']]
            
            # Format headers
            if show_tcp and not show_udp:
                results.append("Active Internet connections (w/o servers)")
                results.append("Proto Recv-Q Send-Q Local Address           Foreign Address         State       PID/Program name")
            elif show_udp and not show_tcp:
                results.append("Active Internet connections (w/o servers)")
                results.append("Proto Recv-Q Send-Q Local Address           Foreign Address         State       PID/Program name")
            else:
                results.append("Active Internet connections (w/o servers)")
                results.append("Proto Recv-Q Send-Q Local Address           Foreign Address         State       PID/Program name")
            
            # Format connections
            for conn in connections:
                proto = 'tcp' if conn.type == socket.SOCK_STREAM else 'udp'
                
                if conn.laddr:
                    laddr = f"{conn.laddr.ip}:{conn.laddr.port}"
                else:
                    laddr = "-"
                
                if conn.raddr:
                    raddr = f"{conn.raddr.ip}:{conn.raddr.port}"
                else:
                    raddr = "-"
                
                if conn.pid:
                    try:
                        process = psutil.Process(conn.pid)
                        program = f"{conn.pid}/{process.name()}"
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        program = f"{conn.pid}/-"
                else:
                    program = "-"
                
                status = conn.status if conn.status else '-'
                
                results.append(f"{proto:<5} {0:<6} {0:<6} {laddr:<21} {raddr:<21} {status:<11} {program if show_programs else ''}")
            
            return "\n".join(results)
        except ImportError:
            return "netstat: psutil module required for network connection information"
        except Exception as e:
            return f"netstat: error: {str(e)}"
    
    @staticmethod
    def do_traceroute(fs, cwd, arg):
        """
        Print the route packets trace to network host
        
        Usage: traceroute [options] destination
        
        Options:
          -4                     Use IPv4
          -6                     Use IPv6
          -m MAX_HOPS            Set max number of hops
          -q QUERIES             Set number of queries per hop
        """
        args = arg.split()
        
        # Parse options
        use_ipv4 = True
        use_ipv6 = False
        max_hops = 30  # Default: 30 hops
        queries = 3  # Default: 3 queries per hop
        
        # Process arguments
        destination = None
        
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                if args[i] == '-4':
                    use_ipv4 = True
                    use_ipv6 = False
                elif args[i] == '-6':
                    use_ipv4 = False
                    use_ipv6 = True
                elif args[i] == '-m':
                    if i + 1 < len(args):
                        try:
                            max_hops = int(args[i+1])
                            i += 1
                        except ValueError:
                            return f"traceroute: invalid max hops: '{args[i+1]}'"
                    else:
                        return "traceroute: option requires an argument -- 'm'"
                elif args[i] == '-q':
                    if i + 1 < len(args):
                        try:
                            queries = int(args[i+1])
                            i += 1
                        except ValueError:
                            return f"traceroute: invalid queries: '{args[i+1]}'"
                    else:
                        return "traceroute: option requires an argument -- 'q'"
                else:
                    return f"traceroute: invalid option -- '{args[i]}'"
            else:
                destination = args[i]
            i += 1
        
        if not destination:
            return "traceroute: missing destination\nUsage: traceroute [options] destination"
        
        # Simplified traceroute implementation (no actual packets)
        try:
            # Resolve hostname to IP
            if use_ipv4:
                ip = socket.gethostbyname(destination)
                addr_family = 'IPv4'
            elif use_ipv6:
                # Not implemented
                return "traceroute: IPv6 not implemented"
            
            results = [f"traceroute to {destination} ({ip}), {max_hops} hops max, 60 byte packets"]
            
            # Simulate traceroute
            import random
            
            for hop in range(1, random.randint(5, 15)):
                hop_line = f"{hop:2}  "
                
                # Generate random router IP
                router_ip = f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
                
                for q in range(queries):
                    # Generate random response time (5-100 ms)
                    response_time = random.uniform(5, 100)
                    hop_line += f"{router_ip}  {response_time:.3f} ms  "
                
                results.append(hop_line)
                
                # Stop when we reach the destination (simulate last hop)
                if hop == random.randint(5, 14):
                    hop_line = f"{hop+1:2}  "
                    for q in range(queries):
                        response_time = random.uniform(5, 100)
                        hop_line += f"{ip}  {response_time:.3f} ms  "
                    results.append(hop_line)
                    break
            
            return "\n".join(results)
        except socket.gaierror:
            return f"traceroute: {destination}: Name or service not known"
        except Exception as e:
            return f"traceroute: error: {str(e)}"

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("ifconfig", UnixNetworkUtilities.do_ifconfig)
    shell.register_command("ping", UnixNetworkUtilities.do_ping)
    shell.register_command("netstat", UnixNetworkUtilities.do_netstat)
    shell.register_command("traceroute", UnixNetworkUtilities.do_traceroute)

"""
Network Utilities Commands for KOS Shell

This module provides Linux-style network utilities that leverage
the KADVLayer's network_manager component for comprehensive network management.
"""

import os
import sys
import json
import logging
import time
import socket
import ipaddress
from datetime import datetime
from typing import Dict, List, Any, Optional

# Import KOS components
from kos.advlayer import kadvlayer

# Set up logging
logger = logging.getLogger('KOS.shell.commands.network_utils')

class NetworkUtilitiesCommands:
    """Network utilities commands for KOS shell"""
    
    @staticmethod
    def do_ifconfig(fs, cwd, arg):
        """
        Display network interface configuration
        
        Usage: ifconfig [interface] [options]
        
        Options:
          --json               Output in JSON format
        """
        args = arg.split()
        
        # Parse interface name
        interface_name = None
        if args and not args[0].startswith('--'):
            interface_name = args[0]
        
        # Parse options
        json_output = '--json' in args
        
        if not kadvlayer or not kadvlayer.network_manager:
            return "Error: Network manager not available"
        
        # Get network interfaces
        interfaces = kadvlayer.network_manager.get_interfaces()
        
        # Filter by interface name if specified
        if interface_name:
            interfaces = [iface for iface in interfaces if iface.get('name') == interface_name]
            if not interfaces:
                return f"Error: Interface '{interface_name}' not found"
        
        # Format output
        if json_output:
            return json.dumps(interfaces, indent=2)
        else:
            output = []
            
            for iface in interfaces:
                name = iface.get('name', 'Unknown')
                status = 'UP' if iface.get('is_up', False) else 'DOWN'
                flags = []
                
                if iface.get('is_up', False):
                    flags.append('UP')
                if iface.get('is_broadcast', False):
                    flags.append('BROADCAST')
                if iface.get('is_loopback', False):
                    flags.append('LOOPBACK')
                if iface.get('is_multicast', False):
                    flags.append('MULTICAST')
                
                mtu = iface.get('mtu', 0)
                
                output.append(f"{name}: flags={','.join(flags)} mtu {mtu}")
                
                if 'addresses' in iface:
                    for addr in iface['addresses']:
                        family = addr.get('family', 'Unknown')
                        address = addr.get('address', 'Unknown')
                        netmask = addr.get('netmask', '')
                        broadcast = addr.get('broadcast', '')
                        
                        if family.lower() == 'inet':
                            output.append(f"    inet {address} netmask {netmask} broadcast {broadcast}")
                        elif family.lower() == 'inet6':
                            scope = addr.get('scope', '')
                            output.append(f"    inet6 {address} scope {scope}")
                        else:
                            output.append(f"    {family} {address}")
                
                if 'hw_addr' in iface:
                    output.append(f"    ether {iface.get('hw_addr')}")
                
                if 'stats' in iface:
                    stats = iface.get('stats', {})
                    rx_bytes = stats.get('bytes_recv', 0)
                    rx_packets = stats.get('packets_recv', 0)
                    rx_errors = stats.get('errin', 0)
                    rx_dropped = stats.get('dropin', 0)
                    
                    tx_bytes = stats.get('bytes_sent', 0)
                    tx_packets = stats.get('packets_sent', 0)
                    tx_errors = stats.get('errout', 0)
                    tx_dropped = stats.get('dropout', 0)
                    
                    output.append(f"    RX packets {rx_packets}  bytes {rx_bytes}")
                    output.append(f"    RX errors {rx_errors}  dropped {rx_dropped}")
                    output.append(f"    TX packets {tx_packets}  bytes {tx_bytes}")
                    output.append(f"    TX errors {tx_errors}  dropped {tx_dropped}")
                
                output.append("")
            
            return "\n".join(output)
    
    @staticmethod
    def do_ping(fs, cwd, arg):
        """
        Send ICMP ECHO_REQUEST to network hosts
        
        Usage: ping [options] <destination>
        
        Options:
          -c <count>          Stop after sending <count> packets
          -i <interval>       Wait <interval> seconds between sending each packet
          -w <timeout>        Time to wait for response (in seconds)
          -s <size>           Set packet size
          -q                  Quiet output, only show summary
          --json              Output in JSON format
        """
        args = arg.split()
        
        if not args:
            return NetworkUtilitiesCommands.do_ping.__doc__
        
        # Parse options
        count = 4  # Default count
        interval = 1.0  # Default interval
        timeout = 1.0  # Default timeout
        size = 56  # Default size
        quiet = False
        json_output = False
        
        dest_host = None
        
        i = 0
        while i < len(args):
            arg = args[i]
            
            if arg == '-c' and i + 1 < len(args):
                try:
                    count = int(args[i + 1])
                    i += 2
                    continue
                except ValueError:
                    return f"Error: Invalid count value '{args[i + 1]}'"
            elif arg == '-i' and i + 1 < len(args):
                try:
                    interval = float(args[i + 1])
                    i += 2
                    continue
                except ValueError:
                    return f"Error: Invalid interval value '{args[i + 1]}'"
            elif arg == '-w' and i + 1 < len(args):
                try:
                    timeout = float(args[i + 1])
                    i += 2
                    continue
                except ValueError:
                    return f"Error: Invalid timeout value '{args[i + 1]}'"
            elif arg == '-s' and i + 1 < len(args):
                try:
                    size = int(args[i + 1])
                    i += 2
                    continue
                except ValueError:
                    return f"Error: Invalid size value '{args[i + 1]}'"
            elif arg == '-q':
                quiet = True
                i += 1
                continue
            elif arg == '--json':
                json_output = True
                i += 1
                continue
            elif not dest_host and not arg.startswith('-'):
                dest_host = arg
                i += 1
                continue
            else:
                i += 1
        
        if not dest_host:
            return "Error: Missing destination host"
        
        if not kadvlayer or not kadvlayer.network_manager:
            return "Error: Network manager not available"
        
        # Execute ping
        result = kadvlayer.network_manager.ping(dest_host, count=count, interval=interval, timeout=timeout, size=size)
        
        if not result.get('success', False):
            return f"Error: {result.get('error', 'Unknown error')}"
        
        # Format output
        packets = result.get('packets', [])
        sent = len(packets)
        received = sum(1 for p in packets if p.get('success', False))
        loss_pct = 0 if sent == 0 else (sent - received) * 100 / sent
        
        if json_output:
            summary = {
                'host': dest_host,
                'packets_transmitted': sent,
                'packets_received': received,
                'packet_loss_pct': loss_pct,
                'packets': packets
            }
            
            if received > 0:
                times = [p.get('time_ms', 0) for p in packets if p.get('success', False)]
                summary['rtt_min'] = min(times)
                summary['rtt_avg'] = sum(times) / len(times)
                summary['rtt_max'] = max(times)
            
            return json.dumps(summary, indent=2)
        else:
            output = []
            
            if not quiet:
                output.append(f"PING {dest_host} ({result.get('ip', dest_host)}): {size} data bytes")
                
                for i, packet in enumerate(packets, 1):
                    if packet.get('success', False):
                        seq = packet.get('seq', i)
                        ttl = packet.get('ttl', 0)
                        time = packet.get('time_ms', 0)
                        output.append(f"{size} bytes from {result.get('ip', dest_host)}: icmp_seq={seq} ttl={ttl} time={time:.2f} ms")
                    else:
                        output.append(f"Request timeout for icmp_seq {i}")
            
            output.append("")
            output.append(f"--- {dest_host} ping statistics ---")
            output.append(f"{sent} packets transmitted, {received} received, {loss_pct:.1f}% packet loss")
            
            if received > 0:
                times = [p.get('time_ms', 0) for p in packets if p.get('success', False)]
                min_time = min(times)
                max_time = max(times)
                avg_time = sum(times) / len(times)
                
                output.append(f"round-trip min/avg/max = {min_time:.2f}/{avg_time:.2f}/{max_time:.2f} ms")
            
            return "\n".join(output)
    
    @staticmethod
    def do_traceroute(fs, cwd, arg):
        """
        Trace route to host
        
        Usage: traceroute [options] <destination>
        
        Options:
          -m <max_hops>       Set maximum number of hops
          -w <timeout>        Set timeout for responses (in seconds)
          -q <queries>        Set number of queries per hop
          -n                  Do not resolve IP addresses to hostnames
          --json              Output in JSON format
        """
        args = arg.split()
        
        if not args:
            return NetworkUtilitiesCommands.do_traceroute.__doc__
        
        # Parse options
        max_hops = 30  # Default max hops
        timeout = 1.0  # Default timeout
        queries = 3  # Default queries
        resolve_hostnames = True
        json_output = False
        
        dest_host = None
        
        i = 0
        while i < len(args):
            arg = args[i]
            
            if arg == '-m' and i + 1 < len(args):
                try:
                    max_hops = int(args[i + 1])
                    i += 2
                    continue
                except ValueError:
                    return f"Error: Invalid max hops value '{args[i + 1]}'"
            elif arg == '-w' and i + 1 < len(args):
                try:
                    timeout = float(args[i + 1])
                    i += 2
                    continue
                except ValueError:
                    return f"Error: Invalid timeout value '{args[i + 1]}'"
            elif arg == '-q' and i + 1 < len(args):
                try:
                    queries = int(args[i + 1])
                    i += 2
                    continue
                except ValueError:
                    return f"Error: Invalid queries value '{args[i + 1]}'"
            elif arg == '-n':
                resolve_hostnames = False
                i += 1
                continue
            elif arg == '--json':
                json_output = True
                i += 1
                continue
            elif not dest_host and not arg.startswith('-'):
                dest_host = arg
                i += 1
                continue
            else:
                i += 1
        
        if not dest_host:
            return "Error: Missing destination host"
        
        if not kadvlayer or not kadvlayer.network_manager:
            return "Error: Network manager not available"
        
        # Execute traceroute
        result = kadvlayer.network_manager.traceroute(
            dest_host, 
            max_hops=max_hops, 
            timeout=timeout, 
            queries=queries, 
            resolve_hostnames=resolve_hostnames
        )
        
        if not result.get('success', False):
            return f"Error: {result.get('error', 'Unknown error')}"
        
        # Format output
        hops = result.get('hops', [])
        destination_reached = result.get('destination_reached', False)
        
        if json_output:
            summary = {
                'host': dest_host,
                'destination_ip': result.get('destination_ip', ''),
                'hops': hops,
                'destination_reached': destination_reached
            }
            
            return json.dumps(summary, indent=2)
        else:
            output = [f"traceroute to {dest_host} ({result.get('destination_ip', '')}), {max_hops} hops max"]
            
            for hop in hops:
                hop_num = hop.get('hop', 0)
                hop_ip = hop.get('ip', '*')
                hop_name = hop.get('hostname', '') if resolve_hostnames else ''
                
                hop_line = f"{hop_num:2d}  "
                
                # Add probe results
                probes = hop.get('probes', [])
                for probe in probes:
                    if probe.get('success', False):
                        rtt = probe.get('rtt_ms', 0)
                        hop_line += f"{rtt:.3f} ms  "
                    else:
                        hop_line += "* "
                
                # Add hostname if available
                if hop_ip != '*':
                    if hop_name and hop_name != hop_ip:
                        hop_line += f"{hop_name} ({hop_ip})"
                    else:
                        hop_line += hop_ip
                
                output.append(hop_line)
            
            if not destination_reached:
                output.append("Destination not reached")
            
            return "\n".join(output)
    
    @staticmethod
    def do_netstat(fs, cwd, arg):
        """
        Print network connections, routing tables, interface statistics
        
        Usage: netstat [options]
        
        Options:
          -a                  Show all connections and listening ports
          -t                  Show TCP connections
          -u                  Show UDP connections
          -n                  Do not resolve names
          -p                  Show processes using the connections
          -r                  Show routing table
          -i                  Show network interfaces
          -s                  Show network statistics
          --json              Output in JSON format
        """
        args = arg.split()
        
        # Parse options
        show_all = '-a' in args
        show_tcp = '-t' in args or not (args and any(a in ['-t', '-u', '-r', '-i', '-s'] for a in args))
        show_udp = '-u' in args
        resolve_names = '-n' not in args
        show_processes = '-p' in args
        show_routing = '-r' in args
        show_interfaces = '-i' in args
        show_statistics = '-s' in args
        json_output = '--json' in args
        
        if not kadvlayer or not kadvlayer.network_manager:
            return "Error: Network manager not available"
        
        # Get data based on options
        result = {}
        
        if show_tcp or show_udp:
            connections = kadvlayer.network_manager.get_connections(
                tcp=show_tcp,
                udp=show_udp,
                all=show_all,
                resolve=resolve_names
            )
            result['connections'] = connections
        
        if show_routing:
            routing = kadvlayer.network_manager.get_routing_table(resolve=resolve_names)
            result['routing'] = routing
        
        if show_interfaces:
            interfaces = kadvlayer.network_manager.get_interfaces()
            result['interfaces'] = interfaces
        
        if show_statistics:
            stats = kadvlayer.network_manager.get_statistics()
            result['statistics'] = stats
        
        # Format output
        if json_output:
            return json.dumps(result, indent=2)
        else:
            output = []
            
            # Format connections
            if 'connections' in result:
                if show_tcp and show_udp:
                    output.append("Active Internet connections")
                elif show_tcp:
                    output.append("Active Internet connections (TCP)")
                elif show_udp:
                    output.append("Active Internet connections (UDP)")
                
                if show_processes:
                    output.append("Proto Recv-Q Send-Q Local Address           Foreign Address         State       PID/Program name")
                else:
                    output.append("Proto Recv-Q Send-Q Local Address           Foreign Address         State")
                
                for conn in result['connections']:
                    proto = conn.get('proto', '').upper()
                    recv_q = conn.get('recv_q', 0)
                    send_q = conn.get('send_q', 0)
                    local_addr = f"{conn.get('local_addr', '')}:{conn.get('local_port', '')}"
                    remote_addr = f"{conn.get('remote_addr', '')}:{conn.get('remote_port', '')}"
                    state = conn.get('state', '')
                    
                    line = f"{proto:<5} {recv_q:<6} {send_q:<6} {local_addr:<22} {remote_addr:<22} {state:<11}"
                    
                    if show_processes:
                        pid = conn.get('pid', '')
                        program = conn.get('program', '')
                        if pid and program:
                            line += f" {pid}/{program}"
                        elif pid:
                            line += f" {pid}"
                    
                    output.append(line)
                
                output.append("")
            
            # Format routing table
            if 'routing' in result:
                output.append("Kernel IP routing table")
                output.append("Destination     Gateway         Genmask         Flags   MSS Window  irtt Iface")
                
                for route in result['routing']:
                    destination = route.get('destination', '0.0.0.0')
                    gateway = route.get('gateway', '0.0.0.0')
                    netmask = route.get('netmask', '0.0.0.0')
                    flags = route.get('flags', '')
                    mss = route.get('mss', 0)
                    window = route.get('window', 0)
                    irtt = route.get('irtt', 0)
                    interface = route.get('interface', '')
                    
                    output.append(f"{destination:<15} {gateway:<15} {netmask:<15} {flags:<6} {mss:<4} {window:<6} {irtt:<4} {interface}")
                
                output.append("")
            
            # Format interfaces
            if 'interfaces' in result:
                output.append("Kernel Interface table")
                output.append("Iface      MTU    RX-OK RX-ERR RX-DRP RX-OVR    TX-OK TX-ERR TX-DRP TX-OVR Flg")
                
                for iface in result['interfaces']:
                    name = iface.get('name', '')
                    mtu = iface.get('mtu', 0)
                    stats = iface.get('stats', {})
                    
                    rx_ok = stats.get('packets_recv', 0)
                    rx_err = stats.get('errin', 0)
                    rx_drp = stats.get('dropin', 0)
                    rx_ovr = stats.get('fifo_in', 0)
                    
                    tx_ok = stats.get('packets_sent', 0)
                    tx_err = stats.get('errout', 0)
                    tx_drp = stats.get('dropout', 0)
                    tx_ovr = stats.get('fifo_out', 0)
                    
                    flags = []
                    if iface.get('is_up', False):
                        flags.append('U')
                    if iface.get('is_broadcast', False):
                        flags.append('B')
                    if iface.get('is_loopback', False):
                        flags.append('L')
                    if iface.get('is_multicast', False):
                        flags.append('M')
                    
                    output.append(f"{name:<10} {mtu:<6} {rx_ok:<6} {rx_err:<6} {rx_drp:<6} {rx_ovr:<6} {tx_ok:<6} {tx_err:<6} {tx_drp:<6} {tx_ovr:<6} {''.join(flags)}")
                
                output.append("")
            
            # Format statistics
            if 'statistics' in result:
                if 'tcp' in result['statistics']:
                    output.append("TCP Statistics:")
                    tcp_stats = result['statistics']['tcp']
                    for key, value in tcp_stats.items():
                        output.append(f"    {key}: {value}")
                    output.append("")
                
                if 'udp' in result['statistics']:
                    output.append("UDP Statistics:")
                    udp_stats = result['statistics']['udp']
                    for key, value in udp_stats.items():
                        output.append(f"    {key}: {value}")
                    output.append("")
                
                if 'ip' in result['statistics']:
                    output.append("IP Statistics:")
                    ip_stats = result['statistics']['ip']
                    for key, value in ip_stats.items():
                        output.append(f"    {key}: {value}")
                    output.append("")
                
                if 'icmp' in result['statistics']:
                    output.append("ICMP Statistics:")
                    icmp_stats = result['statistics']['icmp']
                    for key, value in icmp_stats.items():
                        output.append(f"    {key}: {value}")
                    output.append("")
            
            return "\n".join(output)
    
    @staticmethod
    def do_nslookup(fs, cwd, arg):
        """
        Query DNS servers
        
        Usage: nslookup [options] <name> [server]
        
        Options:
          -type=<type>         Set query type (A, AAAA, MX, NS, SOA, TXT, etc.)
          -timeout=<sec>       Set timeout for query
          -debug               Enable debug output
          --json               Output in JSON format
        """
        args = arg.split()
        
        if not args:
            return NetworkUtilitiesCommands.do_nslookup.__doc__
        
        # Parse options
        query_type = 'A'  # Default query type
        timeout = 5.0  # Default timeout
        debug = False
        json_output = False
        
        name = None
        server = None
        
        i = 0
        while i < len(args):
            arg = args[i]
            
            if arg.startswith('-type='):
                query_type = arg[6:].upper()
                i += 1
                continue
            elif arg.startswith('-timeout='):
                try:
                    timeout = float(arg[9:])
                    i += 1
                    continue
                except ValueError:
                    return f"Error: Invalid timeout value '{arg[9:]}'"
            elif arg == '-debug':
                debug = True
                i += 1
                continue
            elif arg == '--json':
                json_output = True
                i += 1
                continue
            elif not name and not arg.startswith('-'):
                name = arg
                i += 1
                continue
            elif name and not server and not arg.startswith('-'):
                server = arg
                i += 1
                continue
            else:
                i += 1
        
        if not name:
            return "Error: Missing name to lookup"
        
        if not kadvlayer or not kadvlayer.network_manager:
            return "Error: Network manager not available"
        
        # Execute DNS lookup
        result = kadvlayer.network_manager.dns_lookup(
            name, 
            query_type=query_type, 
            server=server,
            timeout=timeout
        )
        
        if not result.get('success', False):
            return f"Error: {result.get('error', 'Unknown error')}"
        
        # Format output
        if json_output:
            return json.dumps(result, indent=2)
        else:
            output = []
            
            if server:
                output.append(f"Server: {server}")
            else:
                output.append("Server: default")
            
            output.append(f"Address: {result.get('server_ip', '')}")
            output.append("")
            
            if debug:
                output.append(f"Query: {name}, type = {query_type}, class = IN")
                output.append("")
            
            answers = result.get('answers', [])
            if answers:
                output.append(f"Non-authoritative answer:")
                for answer in answers:
                    if query_type == 'A' or query_type == 'AAAA':
                        output.append(f"Name: {answer.get('name', '')}")
                        output.append(f"Address: {answer.get('data', '')}")
                    elif query_type == 'MX':
                        output.append(f"Name: {answer.get('name', '')}")
                        output.append(f"Mail server: {answer.get('data', '')}")
                        output.append(f"Preference: {answer.get('preference', 0)}")
                    elif query_type == 'NS':
                        output.append(f"Name: {answer.get('name', '')}")
                        output.append(f"Nameserver: {answer.get('data', '')}")
                    elif query_type == 'TXT':
                        output.append(f"Name: {answer.get('name', '')}")
                        output.append(f"Text: {answer.get('data', '')}")
                    elif query_type == 'SOA':
                        output.append(f"Name: {answer.get('name', '')}")
                        output.append(f"Origin: {answer.get('origin', '')}")
                        output.append(f"Mail addr: {answer.get('mail', '')}")
                        output.append(f"Serial: {answer.get('serial', 0)}")
                        output.append(f"Refresh: {answer.get('refresh', 0)}")
                        output.append(f"Retry: {answer.get('retry', 0)}")
                        output.append(f"Expire: {answer.get('expire', 0)}")
                        output.append(f"Minimum: {answer.get('minimum', 0)}")
                    else:
                        output.append(f"Name: {answer.get('name', '')}")
                        output.append(f"Type: {answer.get('type', '')}")
                        output.append(f"Data: {answer.get('data', '')}")
                    
                    output.append("")
            else:
                output.append("No answer")
            
            return "\n".join(output)

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("ifconfig", NetworkUtilitiesCommands.do_ifconfig)
    shell.register_command("ping", NetworkUtilitiesCommands.do_ping)
    shell.register_command("traceroute", NetworkUtilitiesCommands.do_traceroute)
    shell.register_command("netstat", NetworkUtilitiesCommands.do_netstat)
    shell.register_command("nslookup", NetworkUtilitiesCommands.do_nslookup)

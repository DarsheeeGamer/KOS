"""
System Utilities Commands for KOS Shell

This module provides Linux-style system utilities that leverage
the KADVLayer and KLayer components for comprehensive system management.
"""

import os
import sys
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

# Import KOS components
from kos.advlayer import kadvlayer
from kos.layer import klayer

# Set up logging
logger = logging.getLogger('KOS.shell.commands.system_utils')

class SystemUtilitiesCommands:
    """System utilities commands for KOS shell"""
    
    @staticmethod
    def do_sysinfo(fs, cwd, arg):
        """
        Display comprehensive system information
        
        Usage: sysinfo [option]
        
        Options:
          --cpu       Show CPU information
          --memory    Show memory information
          --disk      Show disk information
          --network   Show network information
          --all       Show all information (default)
          --json      Output in JSON format
        """
        # Parse arguments
        args = arg.split()
        show_cpu = '--cpu' in args or '--all' in args or not args
        show_memory = '--memory' in args or '--all' in args or not args
        show_disk = '--disk' in args or '--all' in args or not args
        show_network = '--network' in args or '--all' in args or not args
        json_output = '--json' in args
        
        # Get system information
        info = {}
        
        if kadvlayer:
            if show_cpu and kadvlayer.system_info:
                info['cpu'] = kadvlayer.system_info.get_cpu_info()
            
            if show_memory and kadvlayer.system_info:
                info['memory'] = kadvlayer.system_info.get_memory_info()
            
            if show_disk and kadvlayer.system_info:
                info['disk'] = kadvlayer.system_info.get_disk_info()
            
            if show_network and kadvlayer.system_info:
                info['network'] = kadvlayer.system_info.get_network_info()
        else:
            return "Error: KADVLayer not available"
        
        # Format output
        if json_output:
            return json.dumps(info, indent=2)
        else:
            # Format human-readable output
            output = []
            
            if 'cpu' in info:
                output.append("CPU Information:")
                output.append(f"  Logical cores: {info['cpu'].get('count_logical', 'N/A')}")
                output.append(f"  Physical cores: {info['cpu'].get('count_physical', 'N/A')}")
                output.append(f"  Current usage: {info['cpu'].get('percent', 'N/A')}%")
                output.append("")
            
            if 'memory' in info:
                memory = info['memory'].get('virtual', {})
                output.append("Memory Information:")
                if memory:
                    total_gb = memory.get('total', 0) / (1024 ** 3)
                    used_gb = memory.get('used', 0) / (1024 ** 3)
                    available_gb = memory.get('available', 0) / (1024 ** 3)
                    output.append(f"  Total: {total_gb:.2f} GB")
                    output.append(f"  Used: {used_gb:.2f} GB ({memory.get('percent', 'N/A')}%)")
                    output.append(f"  Available: {available_gb:.2f} GB")
                output.append("")
            
            if 'disk' in info:
                output.append("Disk Information:")
                for partition in info['disk'].get('partitions', []):
                    total_gb = partition.get('total', 0) / (1024 ** 3)
                    used_gb = partition.get('used', 0) / (1024 ** 3)
                    free_gb = partition.get('free', 0) / (1024 ** 3)
                    output.append(f"  {partition.get('mountpoint', 'N/A')} ({partition.get('device', 'N/A')}):")
                    output.append(f"    Total: {total_gb:.2f} GB")
                    output.append(f"    Used: {used_gb:.2f} GB ({partition.get('percent', 'N/A')}%)")
                    output.append(f"    Free: {free_gb:.2f} GB")
                output.append("")
            
            if 'network' in info:
                output.append("Network Information:")
                output.append(f"  Hostname: {info['network'].get('hostname', 'N/A')}")
                
                if 'interfaces' in info['network']:
                    output.append("  Interfaces:")
                    for interface_name, addresses in info['network']['interfaces'].items():
                        output.append(f"    {interface_name}:")
                        for addr in addresses:
                            output.append(f"      {addr.get('family', 'N/A')}: {addr.get('address', 'N/A')}")
                
                output.append("")
            
            return "\n".join(output)
    
    @staticmethod
    def do_psutil(fs, cwd, arg):
        """
        Display and manage processes
        
        Usage: psutil [command] [options]
        
        Commands:
          list                 List all processes
          top                  Display real-time process information
          kill <pid>           Kill a process
          monitor              Start process monitoring
          monitor stop         Stop process monitoring
        
        Options:
          --all                Include system processes
          --sort=<field>       Sort by field (cpu, memory, name)
          --json               Output in JSON format
        """
        args = arg.split()
        
        if not args:
            return SystemUtilitiesCommands.do_psutil.__doc__
        
        command = args[0]
        options = args[1:]
        
        if command == "list":
            return SystemUtilitiesCommands._psutil_list(options)
        elif command == "top":
            return SystemUtilitiesCommands._psutil_top(options)
        elif command == "kill":
            if len(options) < 1:
                return "Error: Missing process ID"
            return SystemUtilitiesCommands._psutil_kill(options[0], options[1:])
        elif command == "monitor":
            if "stop" in options:
                return SystemUtilitiesCommands._psutil_monitor_stop()
            return SystemUtilitiesCommands._psutil_monitor_start(options)
        else:
            return f"Error: Unknown command '{command}'"
    
    @staticmethod
    def _psutil_list(options):
        """List processes"""
        include_system = '--all' in options
        json_output = '--json' in options
        
        # Get sort field
        sort_field = 'cpu'
        for opt in options:
            if opt.startswith('--sort='):
                sort_field = opt[7:]
        
        if not kadvlayer or not kadvlayer.process_monitor:
            return "Error: Process monitor not available"
        
        # List processes
        processes = kadvlayer.process_monitor.get_tracked_processes()
        
        # Sort processes
        if sort_field == 'cpu':
            processes.sort(key=lambda p: p.get('cpu_percent', 0), reverse=True)
        elif sort_field == 'memory':
            processes.sort(key=lambda p: p.get('memory_percent', 0), reverse=True)
        elif sort_field == 'name':
            processes.sort(key=lambda p: p.get('name', '').lower())
        
        # Format output
        if json_output:
            return json.dumps(processes, indent=2)
        else:
            output = [f"{'PID':<8} {'CPU%':<8} {'MEM%':<8} {'NAME':<20}"]
            
            for proc in processes[:20]:  # Limit to 20 processes
                pid = proc.get('pid', 'N/A')
                cpu = f"{proc.get('cpu_percent', 0):.1f}"
                mem = f"{proc.get('memory_percent', 0):.1f}"
                name = proc.get('name', 'N/A')
                
                output.append(f"{pid:<8} {cpu:<8} {mem:<8} {name:<20}")
            
            return "\n".join(output)

    @staticmethod
    def _psutil_kill(pid, options):
        """Kill a process"""
        try:
            pid = int(pid)
        except ValueError:
            return f"Error: Invalid process ID '{pid}'"
            
        if not kadvlayer or not kadvlayer.process_manager:
            return "Error: Process manager not available"
            
        # Kill the process
        result = kadvlayer.process_manager.kill_process(pid)
        
        if result.get('success', False):
            return f"Process {pid} terminated successfully"
        else:
            return f"Error: {result.get('error', 'Unknown error')}"
    
    @staticmethod
    def do_sysmon(fs, cwd, arg):
        """
        Monitor system resources
        
        Usage: sysmon [command] [options]
        
        Commands:
          start                Start system monitoring
          stop                 Stop system monitoring
          status               Show monitoring status
          report               Generate monitoring report
        
        Options:
          --interval=<sec>     Set monitoring interval in seconds
          --threshold=<pct>    Set alert threshold percentage
          --verbose            Show detailed information
        """
        args = arg.split()
        
        if not args:
            return SystemUtilitiesCommands.do_sysmon.__doc__
        
        command = args[0]
        options = args[1:]
        
        if command == "start":
            # Parse interval option
            interval = 5  # Default interval
            for opt in options:
                if opt.startswith('--interval='):
                    try:
                        interval = int(opt[11:])
                    except ValueError:
                        return f"Error: Invalid interval value in '{opt}'"
            
            if not kadvlayer:
                return "Error: KADVLayer not available"
                
            # Start system monitoring
            result = kadvlayer.start_monitoring()
            
            if all(result.values()):
                return f"System monitoring started with interval {interval}s"
            else:
                failed = [k for k, v in result.items() if not v]
                return f"Some monitors failed to start: {', '.join(failed)}"
                
        elif command == "stop":
            if not kadvlayer:
                return "Error: KADVLayer not available"
                
            # Stop system monitoring
            result = kadvlayer.stop_monitoring()
            
            if all(result.values()):
                return "System monitoring stopped successfully"
            else:
                failed = [k for k, v in result.items() if not v]
                return f"Some monitors failed to stop: {', '.join(failed)}"
                
        elif command == "status":
            if not kadvlayer:
                return "Error: KADVLayer not available"
                
            # Show monitoring status
            is_resource_monitoring = kadvlayer.resource_monitor and kadvlayer.resource_monitor.is_monitoring()
            is_process_monitoring = kadvlayer.process_monitor and kadvlayer.process_monitor.is_monitoring()
            is_hardware_monitoring = kadvlayer.hardware_manager and kadvlayer.hardware_manager.is_monitoring()
            is_network_monitoring = kadvlayer.network_manager and kadvlayer.network_manager.is_monitoring()
            
            output = ["System Monitoring Status:"]
            output.append(f"  Resource Monitor: {'Active' if is_resource_monitoring else 'Inactive'}")
            output.append(f"  Process Monitor: {'Active' if is_process_monitoring else 'Inactive'}")
            output.append(f"  Hardware Monitor: {'Active' if is_hardware_monitoring else 'Inactive'}")
            output.append(f"  Network Monitor: {'Active' if is_network_monitoring else 'Inactive'}")
            
            return "\n".join(output)
            
        elif command == "report":
            if not kadvlayer:
                return "Error: KADVLayer not available"
                
            # Generate system report
            report = kadvlayer.get_system_summary()
            
            # Check for JSON output
            json_output = '--json' in options
            
            if json_output:
                return json.dumps(report, indent=2)
            else:
                # Format human-readable report
                output = ["System Report:"]
                output.append(f"  Time: {datetime.fromtimestamp(report.get('timestamp', 0))}")
                
                # Add CPU information
                if 'resources' in report and 'cpu' in report['resources']:
                    cpu = report['resources']['cpu']
                    output.append("  CPU Usage:")
                    output.append(f"    Overall: {cpu.get('percent', 'N/A')}%")
                    
                # Add Memory information
                if 'resources' in report and 'memory' in report['resources']:
                    memory = report['resources']['memory']
                    output.append("  Memory Usage:")
                    if 'virtual' in memory:
                        virt = memory['virtual']
                        total_gb = virt.get('total', 0) / (1024 ** 3)
                        used_gb = virt.get('used', 0) / (1024 ** 3)
                        output.append(f"    Total: {total_gb:.2f} GB")
                        output.append(f"    Used: {used_gb:.2f} GB ({virt.get('percent', 'N/A')}%)")
                
                # Add Hardware information
                if 'hardware' in report:
                    hw = report['hardware']
                    output.append("  Hardware:")
                    output.append(f"    Devices: {hw.get('devices_count', 0)}")
                    
                # Add Network information
                if 'network' in report:
                    net = report['network']
                    output.append("  Network:")
                    output.append(f"    Interfaces: {net.get('interfaces_count', 0)}")
                
                # Add Process information
                if 'processes' in report:
                    proc = report['processes']
                    output.append("  Processes:")
                    output.append(f"    Count: {proc.get('count', 0)}")
                
                return "\n".join(output)
        else:
            return f"Error: Unknown command '{command}'"

    @staticmethod
    def do_netmon(fs, cwd, arg):
        """
        Monitor network interfaces and connections
        
        Usage: netmon [command] [options]
        
        Commands:
          interfaces           List network interfaces
          connections          List network connections
          ping <host>          Ping a host
          traceroute <host>    Trace route to a host
          scan <network>       Scan network for hosts
          monitor              Start network monitoring
          monitor stop         Stop network monitoring
        
        Options:
          --count=<num>        Number of pings (default: 4)
          --timeout=<sec>      Timeout in seconds
          --json               Output in JSON format
        """
        args = arg.split()
        
        if not args:
            return SystemUtilitiesCommands.do_netmon.__doc__
        
        command = args[0]
        options = args[1:]
        
        if command == "interfaces":
            return SystemUtilitiesCommands._netmon_interfaces(options)
        elif command == "connections":
            return SystemUtilitiesCommands._netmon_connections(options)
        elif command == "ping":
            if len(options) < 1:
                return "Error: Missing host"
            return SystemUtilitiesCommands._netmon_ping(options[0], options[1:])
        elif command == "traceroute":
            if len(options) < 1:
                return "Error: Missing host"
            return SystemUtilitiesCommands._netmon_traceroute(options[0], options[1:])
        elif command == "scan":
            if len(options) < 1:
                return "Error: Missing network address"
            return SystemUtilitiesCommands._netmon_scan(options[0], options[1:])
        elif command == "monitor":
            if "stop" in options:
                return SystemUtilitiesCommands._netmon_monitor_stop()
            return SystemUtilitiesCommands._netmon_monitor_start(options)
        else:
            return f"Error: Unknown command '{command}'"
    
    @staticmethod
    def _netmon_interfaces(options):
        """List network interfaces"""
        json_output = '--json' in options
        
        if not kadvlayer or not kadvlayer.network_manager:
            return "Error: Network manager not available"
        
        # Get network interfaces
        interfaces = kadvlayer.network_manager.get_interfaces()
        
        # Format output
        if json_output:
            return json.dumps(interfaces, indent=2)
        else:
            output = ["Network Interfaces:"]
            
            for iface in interfaces:
                output.append(f"  {iface['name']}:")
                output.append(f"    Status: {'Up' if iface.get('is_up', False) else 'Down'}")
                
                if 'addresses' in iface:
                    output.append("    Addresses:")
                    for addr in iface['addresses']:
                        output.append(f"      {addr.get('family', 'N/A')}: {addr.get('address', 'N/A')}")
                
                if 'stats' in iface:
                    stats = iface['stats']
                    output.append("    Statistics:")
                    output.append(f"      Bytes sent: {stats.get('bytes_sent', 0)}")
                    output.append(f"      Bytes received: {stats.get('bytes_recv', 0)}")
            
            return "\n".join(output)

    @staticmethod
    def _netmon_ping(host, options):
        """Ping a host"""
        # Parse count option
        count = 4  # Default count
        for opt in options:
            if opt.startswith('--count='):
                try:
                    count = int(opt[8:])
                except ValueError:
                    return f"Error: Invalid count value in '{opt}'"
        
        # Parse timeout option
        timeout = 1.0  # Default timeout
        for opt in options:
            if opt.startswith('--timeout='):
                try:
                    timeout = float(opt[10:])
                except ValueError:
                    return f"Error: Invalid timeout value in '{opt}'"
        
        if not kadvlayer or not kadvlayer.network_manager:
            return "Error: Network manager not available"
        
        # Ping the host
        result = kadvlayer.network_manager.ping(host, count=count, timeout=timeout)
        
        if not result.get('success', False):
            return f"Error: {result.get('error', 'Unknown error')}"
        
        # Format output
        packets = result.get('packets', [])
        sent = len(packets)
        received = sum(1 for p in packets if p.get('success', False))
        loss_pct = 0 if sent == 0 else (sent - received) * 100 / sent
        
        output = [f"PING {host}:"]
        
        for i, packet in enumerate(packets, 1):
            if packet.get('success', False):
                output.append(f"  {i}: time={packet.get('time_ms', 0):.2f} ms")
            else:
                output.append(f"  {i}: timeout")
        
        output.append("")
        output.append(f"--- {host} ping statistics ---")
        output.append(f"{sent} packets transmitted, {received} received, {loss_pct:.1f}% packet loss")
        
        if received > 0:
            times = [p.get('time_ms', 0) for p in packets if p.get('success', False)]
            min_time = min(times)
            max_time = max(times)
            avg_time = sum(times) / len(times)
            
            output.append(f"rtt min/avg/max = {min_time:.2f}/{avg_time:.2f}/{max_time:.2f} ms")
        
        return "\n".join(output)

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("sysinfo", SystemUtilitiesCommands.do_sysinfo)
    shell.register_command("psutil", SystemUtilitiesCommands.do_psutil)
    shell.register_command("sysmon", SystemUtilitiesCommands.do_sysmon)
    shell.register_command("netmon", SystemUtilitiesCommands.do_netmon)

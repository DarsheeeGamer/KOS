#!/usr/bin/env python3
"""
KOS svcmon - Service Monitoring Command

This command provides advanced monitoring capabilities for services and system resources:
- Real-time performance metrics for services
- System resource usage monitoring
- Process monitoring with detailed metrics
- Alerting and threshold configuration
"""

import argparse
import os
import sys
import time
import datetime
from typing import List, Dict, Any, Optional

from ...core import service, monitor
from ...core.monitor import ResourceType
from ...utils import formatting, logging

# Initialize the monitoring subsystem
monitor.initialize()

def format_bytes(bytes_value):
    """Format bytes into human-readable form"""
    if bytes_value < 1024:
        return f"{bytes_value} B"
    elif bytes_value < 1024 * 1024:
        return f"{bytes_value / 1024:.1f} KB"
    elif bytes_value < 1024 * 1024 * 1024:
        return f"{bytes_value / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_value / (1024 * 1024 * 1024):.1f} GB"

def monitor_service(args):
    """Monitor a specific service"""
    service_name = args.name
    
    # Get service info
    service_info = service.get_service_status(service_name)
    if not service_info:
        print(f"Service not found: {service_name}", file=sys.stderr)
        return 1
    
    # Track the service for monitoring
    monitor.track_service(service_name)
    
    # Display service information
    print(f"Service: {service_name} ({service_info['service_type']})")
    print(f"Status: {service_info['state'].lower()}")
    print(f"PID: {service_info['pid'] or 'not running'}")
    
    if service_info['pid']:
        # Get detailed metrics
        metrics = monitor.get_service_metrics(service_name)
        
        if metrics:
            print("\nPerformance Metrics:")
            print(f"  CPU Usage: {metrics['cpu_percent']:.1f}%")
            print(f"  Memory: {format_bytes(metrics['memory_info']['rss'])} "
                 f"({metrics['memory_percent']:.1f}% of system memory)")
            
            if 'io_counters' in metrics and metrics['io_counters']:
                print(f"  I/O: {format_bytes(metrics['io_counters']['read_bytes'])} read, "
                     f"{format_bytes(metrics['io_counters']['write_bytes'])} written")
            
            print(f"  Threads: {metrics['num_threads']}")
            
            if 'open_files' in metrics:
                print(f"  Open files: {len(metrics['open_files'])}")
            
            if 'connections' in metrics:
                print(f"  Network connections: {len(metrics['connections'])}")
            
            # Show uptime
            uptime = metrics['uptime']
            uptime_str = ""
            days, remainder = divmod(uptime, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if days > 0:
                uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s"
            elif hours > 0:
                uptime_str = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
            else:
                uptime_str = f"{int(minutes)}m {int(seconds)}s"
            
            print(f"  Uptime: {uptime_str}")
        
        # Show connections if verbose
        if args.verbose and metrics and 'connections' in metrics and metrics['connections']:
            print("\nNetwork Connections:")
            for conn in metrics['connections']:
                local = f"{conn.get('local_address', {}).get('ip', 'unknown')}:{conn.get('local_address', {}).get('port', '?')}"
                remote = "none"
                if 'remote_address' in conn and conn['remote_address']:
                    remote = f"{conn['remote_address'].get('ip', 'unknown')}:{conn['remote_address'].get('port', '?')}"
                
                print(f"  {local} -> {remote} ({conn.get('status', 'unknown')})")
        
        # Show open files if verbose
        if args.verbose and metrics and 'open_files' in metrics and metrics['open_files']:
            print("\nOpen Files:")
            for file in metrics['open_files'][:10]:  # Limit to 10 files
                print(f"  {file['path']} (fd: {file['fd']})")
            
            if len(metrics['open_files']) > 10:
                print(f"  ... and {len(metrics['open_files']) - 10} more files")
    
    # Show service dependencies
    if service_info['dependencies']:
        print("\nDependencies:")
        for dep in service_info['dependencies']:
            dep_status = service.get_service_status(dep)
            status_str = "running" if dep_status and dep_status['state'] == 'RUNNING' else "not running"
            print(f"  {dep}: {status_str}")
    
    # Show service history if available
    if 'restart_history' in service_info and service_info['restart_history']:
        print("\nRestart History:")
        for i, restart in enumerate(service_info['restart_history'][-5:]):  # Show last 5 restarts
            print(f"  {i+1}. {restart['time']} - {restart['reason']}")
    
    # Show performance history if requested
    if args.history and service_info['pid']:
        print("\nPerformance History:")
        history = monitor.get_process_monitor().get_process_history(service_info['pid'], args.history)
        
        if history:
            # Display CPU and memory history
            cpu_values = [h['cpu_percent'] for h in history if 'cpu_percent' in h]
            mem_values = [h['memory_percent'] for h in history if 'memory_percent' in h]
            
            if cpu_values:
                avg_cpu = sum(cpu_values) / len(cpu_values)
                max_cpu = max(cpu_values)
                print(f"  CPU: avg {avg_cpu:.1f}%, max {max_cpu:.1f}%")
            
            if mem_values:
                avg_mem = sum(mem_values) / len(mem_values)
                max_mem = max(mem_values)
                print(f"  Memory: avg {avg_mem:.1f}%, max {max_mem:.1f}%")
        else:
            print("  No history available yet")
    
    return 0

def list_services(args):
    """List all services with monitoring information"""
    services = service.list_services()
    if not services:
        print("No services found")
        return 0
    
    # Format as a table
    headers = ["Name", "Status", "PID", "CPU%", "Memory", "Uptime", "Restarts"]
    rows = []
    
    for svc in services:
        # Get metrics if service is running
        cpu = "n/a"
        memory = "n/a"
        uptime = "n/a"
        
        if svc['pid']:
            metrics = monitor.get_service_metrics(svc['name'])
            
            if metrics:
                cpu = f"{metrics['cpu_percent']:.1f}%"
                memory = format_bytes(metrics['memory_info']['rss'])
                
                uptime_secs = metrics['uptime']
                days, remainder = divmod(uptime_secs, 86400)
                hours, remainder = divmod(remainder, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                if days > 0:
                    uptime = f"{int(days)}d {int(hours)}h"
                elif hours > 0:
                    uptime = f"{int(hours)}h {int(minutes)}m"
                else:
                    uptime = f"{int(minutes)}m {int(seconds)}s"
        
        rows.append([
            svc['name'],
            svc['state'].lower(),
            str(svc['pid'] or 'n/a'),
            cpu,
            memory,
            uptime,
            str(svc['restart_count'])
        ])
    
    print(formatting.format_table(headers, rows))
    return 0

def show_system_resources(args):
    """Show system resource usage"""
    # Start monitoring if not already running
    if not monitor._monitor_thread or not monitor._monitor_thread.is_alive():
        monitor.start_monitoring()
    
    # Get system metrics
    metrics = monitor.get_system_metrics()
    
    # Get system info
    sysinfo = monitor.get_system_info()
    
    # Display system information
    print("System Information:")
    print(f"  Hostname: {sysinfo['hostname']}")
    print(f"  Platform: {sysinfo['platform']['system']} {sysinfo['platform']['release']}")
    print(f"  Architecture: {sysinfo['platform']['machine']}")
    
    # Format uptime
    uptime_secs = sysinfo['uptime']
    days, remainder = divmod(uptime_secs, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    uptime_str = ""
    if days > 0:
        uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s"
    elif hours > 0:
        uptime_str = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
    else:
        uptime_str = f"{int(minutes)}m {int(seconds)}s"
    
    print(f"  Uptime: {uptime_str}")
    
    # CPU information
    print("\nCPU:")
    print(f"  Cores: {sysinfo['cpu']['physical_cores']} physical, {sysinfo['cpu']['total_cores']} logical")
    
    if ResourceType.CPU in metrics:
        cpu_metrics = metrics[ResourceType.CPU]
        
        # Calculate average CPU usage
        avg_cpu = sum(cpu_metrics['percent']) / len(cpu_metrics['percent'])
        print(f"  Usage: {avg_cpu:.1f}% (average)")
        
        # Show per-core usage if verbose
        if args.verbose:
            for i, usage in enumerate(cpu_metrics['percent']):
                print(f"    Core {i}: {usage:.1f}%")
        
        # Show load average
        print(f"  Load average: {cpu_metrics['load_avg'][0]:.2f}, {cpu_metrics['load_avg'][1]:.2f}, {cpu_metrics['load_avg'][2]:.2f}")
    
    # Memory information
    if ResourceType.MEMORY in metrics:
        mem_metrics = metrics[ResourceType.MEMORY]
        
        print("\nMemory:")
        print(f"  Total: {format_bytes(mem_metrics['total'])}")
        print(f"  Used: {format_bytes(mem_metrics['used'])} ({mem_metrics['percent']:.1f}%)")
        print(f"  Free: {format_bytes(mem_metrics['free'])}")
        
        # Show swap if available
        if mem_metrics['swap_total'] > 0:
            print(f"  Swap: {format_bytes(mem_metrics['swap_used'])}/{format_bytes(mem_metrics['swap_total'])} "
                 f"({mem_metrics['swap_percent']:.1f}%)")
    
    # Disk information
    print("\nDisk:")
    if ResourceType.DISK in metrics:
        disk_metrics = metrics[ResourceType.DISK]
        
        for mountpoint, disk_info in disk_metrics.items():
            print(f"  {mountpoint}:")
            print(f"    Device: {disk_info['device']}")
            print(f"    Type: {disk_info['fstype']}")
            print(f"    Size: {format_bytes(disk_info['total'])}")
            print(f"    Used: {format_bytes(disk_info['used'])} ({disk_info['percent']:.1f}%)")
            print(f"    Free: {format_bytes(disk_info['free'])}")
    
    # Network information
    print("\nNetwork:")
    if ResourceType.NETWORK in metrics:
        net_metrics = metrics[ResourceType.NETWORK]
        
        for interface, net_info in net_metrics.items():
            print(f"  {interface}:")
            print(f"    Received: {format_bytes(net_info['bytes_recv'])}")
            print(f"    Sent: {format_bytes(net_info['bytes_sent'])}")
            print(f"    Packets: {net_info['packets_recv']} received, {net_info['packets_sent']} sent")
    
    # Temperature information if available
    if ResourceType.TEMPERATURE in metrics and metrics[ResourceType.TEMPERATURE]:
        print("\nTemperature:")
        temp_metrics = metrics[ResourceType.TEMPERATURE]
        
        for sensor, temp_info in temp_metrics.items():
            print(f"  {sensor}:")
            for reading in temp_info['readings']:
                print(f"    {reading['label']}: {reading['current']}°C")
    
    return 0

def list_processes(args):
    """List top processes by resource usage"""
    # Start monitoring if not already running
    if not monitor._monitor_thread or not monitor._monitor_thread.is_alive():
        monitor.start_monitoring()
    
    # Get top processes
    process_monitor = monitor.get_process_monitor()
    
    # Wait for initial data collection
    print("Collecting process data...")
    time.sleep(2)
    
    # Get all process metrics
    processes = []
    for pid, metrics in process_monitor.current_metrics.items():
        if metrics:
            processes.append(metrics)
    
    # Sort by requested metric
    sort_by = args.sort
    if sort_by == 'cpu':
        processes.sort(key=lambda p: p.get('cpu_percent', 0), reverse=True)
    elif sort_by == 'memory':
        processes.sort(key=lambda p: p.get('memory_percent', 0), reverse=True)
    elif sort_by == 'io':
        # Sort by total I/O (read + write)
        processes.sort(key=lambda p: (
            p.get('io_counters', {}).get('read_bytes', 0) + 
            p.get('io_counters', {}).get('write_bytes', 0)
        ), reverse=True)
    
    # Limit to top N processes
    processes = processes[:args.limit]
    
    # Format as a table
    headers = ["PID", "Name", "CPU%", "Memory", "Threads", "User"]
    
    if sort_by == 'io':
        headers.append("I/O Read")
        headers.append("I/O Write")
    
    rows = []
    
    for proc in processes:
        # Basic process info
        memory = format_bytes(proc['memory_info']['rss']) if 'memory_info' in proc else "n/a"
        
        row = [
            str(proc['pid']),
            proc['name'],
            f"{proc.get('cpu_percent', 0):.1f}%",
            memory,
            str(proc.get('num_threads', 'n/a')),
            proc.get('username', 'n/a')
        ]
        
        # Add I/O info if sorting by I/O
        if sort_by == 'io' and 'io_counters' in proc and proc['io_counters']:
            row.append(format_bytes(proc['io_counters']['read_bytes']))
            row.append(format_bytes(proc['io_counters']['write_bytes']))
        
        rows.append(row)
    
    print(formatting.format_table(headers, rows))
    return 0

def set_alerts(args):
    """Set resource monitoring alert thresholds"""
    # Map command line args to resource types
    resource_map = {
        'cpu': ResourceType.CPU,
        'memory': ResourceType.MEMORY,
        'disk': ResourceType.DISK,
        'temperature': ResourceType.TEMPERATURE
    }
    
    # Check which thresholds to set
    updated = False
    
    for resource_name, resource_type in resource_map.items():
        threshold_arg = getattr(args, resource_name, None)
        if threshold_arg is not None:
            if monitor.set_threshold(resource_type, threshold_arg):
                print(f"Set {resource_name} alert threshold to {threshold_arg}%")
                updated = True
            else:
                print(f"Failed to set {resource_name} alert threshold", file=sys.stderr)
                return 1
    
    if not updated:
        # Show current thresholds
        print("Current alert thresholds:")
        for resource_name, resource_type in resource_map.items():
            threshold = monitor._system_monitor.thresholds.get(resource_type)
            if threshold is not None:
                print(f"  {resource_name}: {threshold}%")
    
    return 0

def main(args=None):
    """Main entry point"""
    parser = argparse.ArgumentParser(description="KOS svcmon - Service Monitoring Command")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Monitor service
    monitor_parser = subparsers.add_parser("service", help="Monitor a specific service")
    monitor_parser.add_argument("name", help="Service name")
    monitor_parser.add_argument("--history", "-n", type=int, default=10,
                               help="Number of history data points to show")
    monitor_parser.add_argument("--verbose", "-v", action="store_true",
                               help="Show detailed information")
    monitor_parser.set_defaults(func=monitor_service)
    
    # List services
    list_parser = subparsers.add_parser("list", help="List all services with monitoring info")
    list_parser.set_defaults(func=list_services)
    
    # System resources
    resources_parser = subparsers.add_parser("resources", help="Show system resource usage")
    resources_parser.add_argument("--verbose", "-v", action="store_true",
                                 help="Show detailed information")
    resources_parser.set_defaults(func=show_system_resources)
    
    # List processes
    processes_parser = subparsers.add_parser("processes", help="List top processes by resource usage")
    processes_parser.add_argument("--sort", "-s", choices=["cpu", "memory", "io"],
                                 default="cpu", help="Sort criterion")
    processes_parser.add_argument("--limit", "-n", type=int, default=10,
                                 help="Number of processes to show")
    processes_parser.set_defaults(func=list_processes)
    
    # Set alerts
    alerts_parser = subparsers.add_parser("alerts", help="Set resource monitoring alert thresholds")
    alerts_parser.add_argument("--cpu", type=float, help="CPU usage threshold (percent)")
    alerts_parser.add_argument("--memory", type=float, help="Memory usage threshold (percent)")
    alerts_parser.add_argument("--disk", type=float, help="Disk usage threshold (percent)")
    alerts_parser.add_argument("--temperature", type=float, help="Temperature threshold (°C)")
    alerts_parser.set_defaults(func=set_alerts)
    
    # Parse arguments
    args = parser.parse_args(args)
    
    if not args.command:
        # Default to system resources
        return show_system_resources(argparse.Namespace(verbose=False))
    
    if not hasattr(args, 'func'):
        parser.print_help()
        return 1
    
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())

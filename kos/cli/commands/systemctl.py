#!/usr/bin/env python3
"""
KOS systemctl - Service Control Command

This command provides systemd-like service management capabilities, including:
- Creating and configuring services
- Starting, stopping, and restarting services
- Viewing service status and logs
- Managing service dependencies
- Enabling and disabling services
"""

import argparse
import os
import sys
import time
from typing import List, Dict, Any, Optional

from ...core import service
from ...core.service import ServiceType, RestartPolicy, ServiceState
from ...utils import formatting, logging

# Initialize the service subsystem
service.initialize()

def format_service_status(status: Dict[str, Any]) -> str:
    """Format service status for display"""
    if not status:
        return "Service not found"
    
    uptime_str = ""
    if status.get('uptime'):
        uptime_secs = int(status['uptime'])
        days, remainder = divmod(uptime_secs, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if days > 0:
            uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
        elif hours > 0:
            uptime_str = f"{hours}h {minutes}m {seconds}s"
        else:
            uptime_str = f"{minutes}m {seconds}s"
    
    lines = [
        f"{status['name']} - {status['description']}",
        f"   Loaded: loaded ({status['service_type']}; {status['restart_policy'].lower()} restart)",
        f"   Active: {status['state'].lower()} " + 
        (f"(running) since {time.ctime(time.time() - status['uptime'])}; {uptime_str} ago" 
         if status['state'] == 'RUNNING' else ""),
        f"    PID: {status['pid'] or 'n/a'}",
        f" Status: {status['state'].lower()}",
        f"  Tasks: 1" + (f" (running)" if status['state'] == 'RUNNING' else ""),
        f"   CPU: {status['cpu_usage']:.1f}%",
        f"Memory: {formatting.human_readable_size(status['memory_usage'])}",
        f"    IO: {formatting.human_readable_size(status['io_read'])} read, " +
        f"{formatting.human_readable_size(status['io_write'])} written"
    ]
    
    if status['dependencies']:
        lines.append("Dependencies:")
        for dep in status['dependencies']:
            lines.append(f"   {dep}")
    
    if status['restart_count'] > 0:
        lines.append(f"Restarts: {status['restart_count']}")
    
    return "\n".join(lines)

def create_service(args):
    """Create a new service"""
    # Convert string arguments to enums
    service_type = ServiceType[args.type.upper()]
    restart_policy = RestartPolicy[args.restart_policy.upper()]
    
    # Parse environment variables
    env = {}
    if args.environment:
        for env_var in args.environment:
            if '=' in env_var:
                key, value = env_var.split('=', 1)
                env[key] = value
    
    # Create the service
    svc = service.create_service(
        name=args.name,
        description=args.description,
        exec_start=args.exec_start,
        service_type=service_type,
        restart=restart_policy,
        working_directory=args.working_directory,
        user=args.user,
        environment=env,
        dependencies=args.requires,
        conflicts=args.conflicts
    )
    
    if svc:
        print(f"Created service: {args.name}")
    else:
        print(f"Failed to create service: {args.name}", file=sys.stderr)
        return 1
    
    # Start the service if requested
    if args.start:
        if service.start_service(args.name):
            print(f"Started service: {args.name}")
        else:
            print(f"Failed to start service: {args.name}", file=sys.stderr)
            return 1
    
    return 0

def start_service(args):
    """Start a service"""
    if service.start_service(args.name):
        print(f"Started service: {args.name}")
        return 0
    else:
        print(f"Failed to start service: {args.name}", file=sys.stderr)
        return 1

def stop_service(args):
    """Stop a service"""
    if service.stop_service(args.name):
        print(f"Stopped service: {args.name}")
        return 0
    else:
        print(f"Failed to stop service: {args.name}", file=sys.stderr)
        return 1

def restart_service(args):
    """Restart a service"""
    if service.restart_service(args.name):
        print(f"Restarted service: {args.name}")
        return 0
    else:
        print(f"Failed to restart service: {args.name}", file=sys.stderr)
        return 1

def reload_service(args):
    """Reload service configuration"""
    svc = service.get_service_status(args.name)
    if not svc:
        print(f"Service not found: {args.name}", file=sys.stderr)
        return 1
    
    if service.reload_service(args.name):
        print(f"Reloaded service: {args.name}")
        return 0
    else:
        print(f"Failed to reload service: {args.name}", file=sys.stderr)
        return 1

def status_service(args):
    """Show service status"""
    if args.name:
        # Show status for a specific service
        status = service.get_service_status(args.name)
        if status:
            print(format_service_status(status))
            return 0
        else:
            print(f"Service not found: {args.name}", file=sys.stderr)
            return 1
    else:
        # Show status for all services
        services = service.list_services()
        if not services:
            print("No services found")
            return 0
        
        # Format as a table
        headers = ["Name", "Description", "Status", "PID"]
        rows = []
        
        for svc in services:
            rows.append([
                svc['name'],
                svc['description'][:30] + ('...' if len(svc['description']) > 30 else ''),
                svc['state'].lower(),
                str(svc['pid'] or 'n/a')
            ])
        
        print(formatting.format_table(headers, rows))
        return 0

def list_services(args):
    """List all services"""
    services = service.list_services()
    if not services:
        print("No services found")
        return 0
    
    # Format as a table
    headers = ["Name", "Description", "Status", "Uptime", "Restarts"]
    rows = []
    
    for svc in services:
        uptime = "n/a"
        if svc['uptime'] is not None:
            uptime_secs = int(svc['uptime'])
            days, remainder = divmod(uptime_secs, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if days > 0:
                uptime = f"{days}d {hours}h"
            elif hours > 0:
                uptime = f"{hours}h {minutes}m"
            else:
                uptime = f"{minutes}m {seconds}s"
        
        rows.append([
            svc['name'],
            svc['description'][:30] + ('...' if len(svc['description']) > 30 else ''),
            svc['state'].lower(),
            uptime,
            str(svc['restart_count'])
        ])
    
    print(formatting.format_table(headers, rows))
    return 0

def delete_service(args):
    """Delete a service"""
    if service.delete_service(args.name):
        print(f"Deleted service: {args.name}")
        return 0
    else:
        print(f"Failed to delete service: {args.name}", file=sys.stderr)
        return 1

def main(args=None):
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="KOS systemctl - Service Control Command"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Create service
    create_parser = subparsers.add_parser("create", help="Create a new service")
    create_parser.add_argument("name", help="Service name")
    create_parser.add_argument("--exec-start", required=True, help="Command to execute")
    create_parser.add_argument("--description", help="Service description")
    create_parser.add_argument("--type", default="simple", 
                              choices=["simple", "forking", "oneshot", "notify", "idle"],
                              help="Service type")
    create_parser.add_argument("--restart", "--restart-policy", dest="restart_policy", 
                              default="on_failure",
                              choices=["no", "on_success", "on_failure", "on_abnormal", 
                                      "on_watchdog", "on_abort", "always"],
                              help="Restart policy")
    create_parser.add_argument("--working-directory", help="Working directory")
    create_parser.add_argument("--user", help="User to run as")
    create_parser.add_argument("--environment", "-e", action="append", 
                              help="Environment variables (KEY=VALUE)")
    create_parser.add_argument("--requires", action="append", default=[],
                              help="Services that must be running before this one")
    create_parser.add_argument("--conflicts", action="append", default=[],
                              help="Services that cannot run alongside this one")
    create_parser.add_argument("--start", action="store_true",
                              help="Start the service after creation")
    create_parser.set_defaults(func=create_service)
    
    # Start service
    start_parser = subparsers.add_parser("start", help="Start a service")
    start_parser.add_argument("name", help="Service name")
    start_parser.set_defaults(func=start_service)
    
    # Stop service
    stop_parser = subparsers.add_parser("stop", help="Stop a service")
    stop_parser.add_argument("name", help="Service name")
    stop_parser.set_defaults(func=stop_service)
    
    # Restart service
    restart_parser = subparsers.add_parser("restart", help="Restart a service")
    restart_parser.add_argument("name", help="Service name")
    restart_parser.set_defaults(func=restart_service)
    
    # Reload service
    reload_parser = subparsers.add_parser("reload", help="Reload service configuration")
    reload_parser.add_argument("name", help="Service name")
    reload_parser.set_defaults(func=reload_service)
    
    # Service status
    status_parser = subparsers.add_parser("status", help="Show service status")
    status_parser.add_argument("name", nargs="?", help="Service name (optional)")
    status_parser.set_defaults(func=status_service)
    
    # List services
    list_parser = subparsers.add_parser("list", help="List all services")
    list_parser.set_defaults(func=list_services)
    
    # Delete service
    delete_parser = subparsers.add_parser("delete", help="Delete a service")
    delete_parser.add_argument("name", help="Service name")
    delete_parser.set_defaults(func=delete_service)
    
    # Parse arguments
    args = parser.parse_args(args)
    
    if not args.command:
        parser.print_help()
        return 1
    
    if not hasattr(args, 'func'):
        parser.print_help()
        return 1
    
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())

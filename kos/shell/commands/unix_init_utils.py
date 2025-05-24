"""
Unix-like System Initialization Utilities for KOS Shell

This module provides Linux/Unix-like init system and service management commands for KOS.
"""

import os
import sys
import time
import logging
import threading
import signal
import subprocess
import re
from typing import Dict, List, Any, Optional, Union

# Import KOS components
from kos.layer import klayer

# Set up logging
logger = logging.getLogger('KOS.shell.commands.unix_init_utils')

# Service registry
SERVICES = {}
SERVICE_LOCK = threading.Lock()

class UnixInitUtilities:
    """Unix-like init system commands for KOS shell"""
    
    @staticmethod
    def do_service(fs, cwd, arg):
        """
        Run a System V init script
        
        Usage: service NAME COMMAND [OPTIONS]
        
        Commands:
          start           Start the service
          stop            Stop the service
          restart         Restart the service
          reload          Reload configuration
          status          Show current status of the service
        """
        args = arg.split()
        
        if len(args) < 2:
            return "service: usage: service NAME COMMAND [OPTIONS]"
        
        name = args[0]
        command = args[1]
        options = args[2:]
        
        # Initialize service registry if needed
        with SERVICE_LOCK:
            if name not in SERVICES:
                SERVICES[name] = {
                    'name': name,
                    'status': 'stopped',
                    'pid': None,
                    'uptime': 0,
                    'start_time': 0,
                    'config': {}
                }
        
        # Execute command
        if command == 'start':
            return UnixInitUtilities._start_service(name, options)
        elif command == 'stop':
            return UnixInitUtilities._stop_service(name, options)
        elif command == 'restart':
            stop_result = UnixInitUtilities._stop_service(name, options)
            start_result = UnixInitUtilities._start_service(name, options)
            return f"{stop_result}\n{start_result}"
        elif command == 'reload':
            return UnixInitUtilities._reload_service(name, options)
        elif command == 'status':
            return UnixInitUtilities._service_status(name, options)
        else:
            return f"service: unknown command: {command}"
    
    @staticmethod
    def _start_service(name, options):
        """Start a service"""
        with SERVICE_LOCK:
            if name not in SERVICES:
                return f"service: service {name} not found"
            
            service = SERVICES[name]
            
            if service['status'] == 'running':
                return f"service {name} is already running"
            
            # Simulate starting the service
            service['status'] = 'running'
            service['pid'] = 1000 + len(SERVICES)
            service['start_time'] = time.time()
            service['uptime'] = 0
            
            return f"Starting {name} service: [ OK ]"
    
    @staticmethod
    def _stop_service(name, options):
        """Stop a service"""
        with SERVICE_LOCK:
            if name not in SERVICES:
                return f"service: service {name} not found"
            
            service = SERVICES[name]
            
            if service['status'] == 'stopped':
                return f"service {name} is already stopped"
            
            # Simulate stopping the service
            service['status'] = 'stopped'
            service['pid'] = None
            service['uptime'] = time.time() - service['start_time']
            
            return f"Stopping {name} service: [ OK ]"
    
    @staticmethod
    def _reload_service(name, options):
        """Reload service configuration"""
        with SERVICE_LOCK:
            if name not in SERVICES:
                return f"service: service {name} not found"
            
            service = SERVICES[name]
            
            if service['status'] == 'stopped':
                return f"service {name} is not running"
            
            # Simulate reloading the service
            return f"Reloading {name} service configuration: [ OK ]"
    
    @staticmethod
    def _service_status(name, options):
        """Get service status"""
        with SERVICE_LOCK:
            if name not in SERVICES:
                return f"service: service {name} not found"
            
            service = SERVICES[name]
            
            result = [f"{name} service status:"]
            
            if service['status'] == 'running':
                uptime = time.time() - service['start_time']
                uptime_str = UnixInitUtilities._format_uptime(uptime)
                result.append(f"  Status: running")
                result.append(f"  PID: {service['pid']}")
                result.append(f"  Uptime: {uptime_str}")
            else:
                result.append(f"  Status: stopped")
                if service['uptime'] > 0:
                    uptime_str = UnixInitUtilities._format_uptime(service['uptime'])
                    result.append(f"  Last uptime: {uptime_str}")
            
            return "\n".join(result)
    
    @staticmethod
    def _format_uptime(seconds):
        """Format uptime in human readable format"""
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if days > 0:
            return f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s"
        elif hours > 0:
            return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
        elif minutes > 0:
            return f"{int(minutes)}m {int(seconds)}s"
        else:
            return f"{int(seconds)}s"
    
    @staticmethod
    def do_systemctl(fs, cwd, arg):
        """
        Control the systemd system and service manager
        
        Usage: systemctl [options] COMMAND [NAME...]
        
        Commands:
          start            Start (activate) one or more units
          stop             Stop (deactivate) one or more units
          restart          Restart one or more units
          reload           Reload one or more units
          status           Show runtime status of one or more units
          enable           Enable one or more unit files
          disable          Disable one or more unit files
          list-units       List loaded units
          list-unit-files  List installed unit files
        """
        args = arg.split()
        
        if not args:
            return "systemctl: command required"
        
        command = args[0]
        names = args[1:]
        
        # Execute command
        if command in ['start', 'stop', 'restart', 'reload', 'status'] and names:
            # Service control commands
            results = []
            for name in names:
                # Add .service suffix if not specified
                if not name.endswith('.service'):
                    name = name + '.service'
                
                # Convert to service name without .service
                service_name = name[:-8] if name.endswith('.service') else name
                
                if command == 'start':
                    results.append(UnixInitUtilities._start_service(service_name, []))
                elif command == 'stop':
                    results.append(UnixInitUtilities._stop_service(service_name, []))
                elif command == 'restart':
                    stop_result = UnixInitUtilities._stop_service(service_name, [])
                    start_result = UnixInitUtilities._start_service(service_name, [])
                    results.append(f"{stop_result}\n{start_result}")
                elif command == 'reload':
                    results.append(UnixInitUtilities._reload_service(service_name, []))
                elif command == 'status':
                    results.append(UnixInitUtilities._service_status(service_name, []))
            
            return "\n".join(results)
        
        elif command == 'enable' and names:
            # Enable services
            results = []
            for name in names:
                # Add .service suffix if not specified
                if not name.endswith('.service'):
                    name = name + '.service'
                
                # Convert to service name without .service
                service_name = name[:-8] if name.endswith('.service') else name
                
                # Initialize service registry if needed
                with SERVICE_LOCK:
                    if service_name not in SERVICES:
                        SERVICES[service_name] = {
                            'name': service_name,
                            'status': 'stopped',
                            'pid': None,
                            'uptime': 0,
                            'start_time': 0,
                            'config': {},
                            'enabled': True
                        }
                    else:
                        SERVICES[service_name]['enabled'] = True
                
                results.append(f"Created symlink /etc/systemd/system/multi-user.target.wants/{name} → /usr/lib/systemd/system/{name}.")
            
            return "\n".join(results)
        
        elif command == 'disable' and names:
            # Disable services
            results = []
            for name in names:
                # Add .service suffix if not specified
                if not name.endswith('.service'):
                    name = name + '.service'
                
                # Convert to service name without .service
                service_name = name[:-8] if name.endswith('.service') else name
                
                # Initialize service registry if needed
                with SERVICE_LOCK:
                    if service_name in SERVICES:
                        SERVICES[service_name]['enabled'] = False
                
                results.append(f"Removed /etc/systemd/system/multi-user.target.wants/{name}.")
            
            return "\n".join(results)
        
        elif command == 'list-units':
            # List all loaded units
            with SERVICE_LOCK:
                results = ["UNIT                    LOAD   ACTIVE SUB     DESCRIPTION"]
                
                for name, service in sorted(SERVICES.items()):
                    status = "active" if service['status'] == 'running' else "inactive"
                    sub = "running" if service['status'] == 'running' else "dead"
                    
                    unit_name = name + ".service"
                    description = f"{name.capitalize()} service"
                    
                    results.append(f"{unit_name:<24} loaded {status:<6} {sub:<7} {description}")
                
                if not SERVICES:
                    results.append("0 loaded units listed.")
                else:
                    results.append(f"{len(SERVICES)} loaded units listed.")
            
            return "\n".join(results)
        
        elif command == 'list-unit-files':
            # List all unit files
            with SERVICE_LOCK:
                results = ["UNIT FILE                 STATE"]
                
                for name, service in sorted(SERVICES.items()):
                    state = "enabled" if service.get('enabled', False) else "disabled"
                    
                    unit_name = name + ".service"
                    
                    results.append(f"{unit_name:<25} {state}")
                
                if not SERVICES:
                    results.append("0 unit files listed.")
                else:
                    results.append(f"{len(SERVICES)} unit files listed.")
            
            return "\n".join(results)
        
        else:
            return f"systemctl: unknown command {command}"
    
    @staticmethod
    def do_init(fs, cwd, arg):
        """
        Change SysV runlevel
        
        Usage: init RUNLEVEL
        
        Change the system runlevel to RUNLEVEL.
        """
        args = arg.split()
        
        if not args:
            return "init: usage: init RUNLEVEL"
        
        runlevel = args[0]
        
        # Validate runlevel
        if runlevel not in ['0', '1', '2', '3', '4', '5', '6', 'S', 's']:
            return f"init: invalid runlevel: {runlevel}"
        
        # Simulate runlevel change
        if runlevel == '0':
            return "Shutting down system... (simulated)"
        elif runlevel in ['S', 's', '1']:
            return "Changing to single-user mode... (simulated)"
        elif runlevel == '6':
            return "Rebooting system... (simulated)"
        else:
            return f"Changing to runlevel {runlevel}... (simulated)"
    
    @staticmethod
    def do_runlevel(fs, cwd, arg):
        """
        Print the previous and current SysV runlevel
        
        Usage: runlevel
        """
        # Simulate runlevel
        prev_level = 'N'
        curr_level = '5'  # Assume normal multi-user graphical mode
        
        return f"{prev_level} {curr_level}"
    
    @staticmethod
    def do_shutdown(fs, cwd, arg):
        """
        Shutdown or restart the system
        
        Usage: shutdown [options] [time] [message]
        
        Options:
          -h      Halt the system
          -r      Reboot the system
          -c      Cancel a pending shutdown
        """
        args = arg.split()
        
        # Parse options
        halt = False
        reboot = False
        cancel = False
        
        if not args:
            return "shutdown: time expected"
        
        i = 0
        while i < len(args):
            if args[i] == '-h':
                halt = True
                i += 1
            elif args[i] == '-r':
                reboot = True
                i += 1
            elif args[i] == '-c':
                cancel = True
                i += 1
            else:
                break
        
        # Handle cancel
        if cancel:
            return "Shutdown cancelled. (simulated)"
        
        # Parse time (if specified)
        time_spec = args[i] if i < len(args) else "now"
        i += 1
        
        # Parse message (if specified)
        message = " ".join(args[i:]) if i < len(args) else ""
        
        # Simulate shutdown
        if halt:
            action = "halt"
        elif reboot:
            action = "reboot"
        else:
            action = "power-off"
        
        if time_spec == "now":
            when = "now"
        else:
            when = time_spec
        
        return f"Shutdown scheduled for {when}, {action}. {message} (simulated)"

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("service", UnixInitUtilities.do_service)
    shell.register_command("systemctl", UnixInitUtilities.do_systemctl)
    shell.register_command("init", UnixInitUtilities.do_init)
    shell.register_command("runlevel", UnixInitUtilities.do_runlevel)
    shell.register_command("shutdown", UnixInitUtilities.do_shutdown)
    shell.register_command("reboot", lambda fs, cwd, arg: UnixInitUtilities.do_shutdown(fs, cwd, "-r now"))
    shell.register_command("halt", lambda fs, cwd, arg: UnixInitUtilities.do_shutdown(fs, cwd, "-h now"))
    shell.register_command("poweroff", lambda fs, cwd, arg: UnixInitUtilities.do_shutdown(fs, cwd, "now"))

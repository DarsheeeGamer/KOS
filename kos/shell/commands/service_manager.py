"""
Service Management Utilities for KOS Shell

This module provides systemd-like service management commands for KOS.
"""

import os
import sys
import time
import logging
import json
import shlex
import datetime
from typing import Dict, List, Any, Optional, Union

# Import KOS components
from kos.layer import klayer
from kos.services import ServiceManager, ServiceState, ServiceType, ServiceRestartPolicy

# Set up logging
logger = logging.getLogger('KOS.shell.commands.service_manager')

class ServiceUtilities:
    """Service management commands for KOS shell"""
    
    @staticmethod
    def do_systemctl(fs, cwd, arg):
        """
        Control the KOS service manager (systemctl-like interface)
        
        Usage: systemctl COMMAND [options] [SERVICE...]
        
        Commands:
          start SERVICE...         Start one or more services
          stop SERVICE...          Stop one or more services
          restart SERVICE...       Restart one or more services
          reload SERVICE...        Reload one or more services
          status [SERVICE...]      Show service status
          enable SERVICE...        Enable one or more services
          disable SERVICE...       Disable one or more services
          is-active SERVICE...     Check if service is active
          is-failed SERVICE...     Check if service is failed
          list-units               List loaded services
          list-unit-files          List available service files
          daemon-reload            Reload service manager configuration
          cat SERVICE...           Show service file content
        """
        args = shlex.split(arg)
        
        if not args:
            return ServiceUtilities.do_systemctl.__doc__
        
        command = args[0]
        options = args[1:]
        
        # Process commands
        if command == "start":
            return ServiceUtilities._systemctl_start(options)
        elif command == "stop":
            return ServiceUtilities._systemctl_stop(options)
        elif command == "restart":
            return ServiceUtilities._systemctl_restart(options)
        elif command == "reload":
            return ServiceUtilities._systemctl_reload(options)
        elif command == "status":
            return ServiceUtilities._systemctl_status(options)
        elif command == "enable":
            return ServiceUtilities._systemctl_enable(options)
        elif command == "disable":
            return ServiceUtilities._systemctl_disable(options)
        elif command == "is-active":
            return ServiceUtilities._systemctl_is_active(options)
        elif command == "is-failed":
            return ServiceUtilities._systemctl_is_failed(options)
        elif command == "list-units":
            return ServiceUtilities._systemctl_list_units(options)
        elif command == "list-unit-files":
            return ServiceUtilities._systemctl_list_unit_files(options)
        elif command == "daemon-reload":
            return ServiceUtilities._systemctl_daemon_reload(options)
        elif command == "cat":
            return ServiceUtilities._systemctl_cat(options)
        else:
            return f"systemctl: unknown command '{command}'"
    
    @staticmethod
    def do_service(fs, cwd, arg):
        """
        Run a service command
        
        Usage: service SERVICE COMMAND [options]
        
        Commands:
          start           Start service
          stop            Stop service
          restart         Restart service
          reload          Reload service
          status          Check service status
        """
        args = shlex.split(arg)
        
        if len(args) < 2:
            return ServiceUtilities.do_service.__doc__
        
        service_name = args[0]
        command = args[1]
        options = args[2:]
        
        # Process commands
        if command == "start":
            return ServiceUtilities._service_start(service_name, options)
        elif command == "stop":
            return ServiceUtilities._service_stop(service_name, options)
        elif command == "restart":
            return ServiceUtilities._service_restart(service_name, options)
        elif command == "reload":
            return ServiceUtilities._service_reload(service_name, options)
        elif command == "status":
            return ServiceUtilities._service_status(service_name, options)
        else:
            return f"service: unknown command '{command}'"
    
    @staticmethod
    def _systemctl_start(options):
        """Start one or more services"""
        if not options:
            return "systemctl start: no services specified"
        
        results = []
        for service_name in options:
            success, message = ServiceManager.start_service(service_name)
            results.append(f"{service_name}: {message}")
        
        return "\n".join(results)
    
    @staticmethod
    def _systemctl_stop(options):
        """Stop one or more services"""
        if not options:
            return "systemctl stop: no services specified"
        
        results = []
        for service_name in options:
            success, message = ServiceManager.stop_service(service_name)
            results.append(f"{service_name}: {message}")
        
        return "\n".join(results)
    
    @staticmethod
    def _systemctl_restart(options):
        """Restart one or more services"""
        if not options:
            return "systemctl restart: no services specified"
        
        results = []
        for service_name in options:
            success, message = ServiceManager.restart_service(service_name)
            results.append(f"{service_name}: {message}")
        
        return "\n".join(results)
    
    @staticmethod
    def _systemctl_reload(options):
        """Reload one or more services"""
        if not options:
            return "systemctl reload: no services specified"
        
        results = []
        for service_name in options:
            success, message = ServiceManager.reload_service(service_name)
            results.append(f"{service_name}: {message}")
        
        return "\n".join(results)
    
    @staticmethod
    def _systemctl_status(options):
        """Show service status"""
        if not options:
            # Show all services
            services = ServiceManager.list_services()
            
            if not services:
                return "No services found"
            
            results = ["SERVICE              LOAD   ACTIVE   SUB     DESCRIPTION"]
            
            for service in services:
                name = service.name
                load = "loaded"
                active = service.state.value
                sub = active  # Sub-state, using same as active for simplicity
                description = service.description
                
                results.append(f"{name:<20} {load:<6} {active:<8} {sub:<7} {description}")
            
            return "\n".join(results)
        
        # Show specific service(s)
        results = []
        for service_name in options:
            success, message, status = ServiceManager.status_service(service_name)
            
            if not success:
                results.append(f"● {service_name} - not found")
                continue
            
            # Format detailed status output
            uptime = "0s"
            if status.get("uptime", 0) > 0:
                uptime_sec = status.get("uptime", 0)
                if uptime_sec < 60:
                    uptime = f"{uptime_sec}s"
                elif uptime_sec < 3600:
                    uptime = f"{uptime_sec // 60}min {uptime_sec % 60}s"
                else:
                    uptime = f"{uptime_sec // 3600}h {(uptime_sec % 3600) // 60}min {uptime_sec % 60}s"
            
            state_color = ""
            if status.get("state") == "active":
                state_color = "active (running)"
            elif status.get("state") == "failed":
                state_color = "failed (failed)"
            else:
                state_color = f"{status.get('state')} ({status.get('state')})"
            
            service_output = [
                f"● {status.get('name')} - {status.get('description')}",
                f"   Loaded: loaded",
                f"   Active: {state_color} since {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}; {uptime} ago",
                f"   Process: {status.get('pid') or 'n/a'} (command={status.get('command')})",
                f"   Main PID: {status.get('pid') or 'n/a'}",
                f"   CGroup: /{status.get('name')}",
                f"           └─{status.get('pid') or 'n/a'} {status.get('command')}"
            ]
            
            results.append("\n".join(service_output))
        
        return "\n\n".join(results)
    
    @staticmethod
    def _systemctl_enable(options):
        """Enable one or more services (auto-start at boot)"""
        if not options:
            return "systemctl enable: no services specified"
        
        # In our simplified model, this just means setting restart policy to always
        results = []
        for service_name in options:
            service = ServiceManager.get_service(service_name)
            
            if not service:
                results.append(f"{service_name}: service not found")
                continue
            
            # Update restart policy
            service.restart = ServiceRestartPolicy.ALWAYS
            
            # Save services
            service_dir = os.path.join(os.path.expanduser('~'), '.kos', 'services')
            service_db = os.path.join(service_dir, 'services.json')
            ServiceManager.save_services(service_db)
            
            results.append(f"{service_name}: enabled")
        
        return "\n".join(results)
    
    @staticmethod
    def _systemctl_disable(options):
        """Disable one or more services (no auto-start at boot)"""
        if not options:
            return "systemctl disable: no services specified"
        
        # In our simplified model, this just means setting restart policy to no
        results = []
        for service_name in options:
            service = ServiceManager.get_service(service_name)
            
            if not service:
                results.append(f"{service_name}: service not found")
                continue
            
            # Update restart policy
            service.restart = ServiceRestartPolicy.NO
            
            # Save services
            service_dir = os.path.join(os.path.expanduser('~'), '.kos', 'services')
            service_db = os.path.join(service_dir, 'services.json')
            ServiceManager.save_services(service_db)
            
            results.append(f"{service_name}: disabled")
        
        return "\n".join(results)
    
    @staticmethod
    def _systemctl_is_active(options):
        """Check if service is active"""
        if not options:
            return "systemctl is-active: no services specified"
        
        results = []
        for service_name in options:
            service = ServiceManager.get_service(service_name)
            
            if not service:
                results.append("unknown")
                continue
            
            if service.state == ServiceState.ACTIVE:
                results.append("active")
            else:
                results.append("inactive")
        
        return "\n".join(results)
    
    @staticmethod
    def _systemctl_is_failed(options):
        """Check if service is failed"""
        if not options:
            return "systemctl is-failed: no services specified"
        
        results = []
        for service_name in options:
            service = ServiceManager.get_service(service_name)
            
            if not service:
                results.append("unknown")
                continue
            
            if service.state == ServiceState.FAILED:
                results.append("failed")
            else:
                results.append("active")
        
        return "\n".join(results)
    
    @staticmethod
    def _systemctl_list_units(options):
        """List loaded services"""
        services = ServiceManager.list_services()
        
        if not services:
            return "No services found"
        
        results = ["UNIT                   LOAD   ACTIVE   SUB     DESCRIPTION"]
        
        for service in services:
            name = f"{service.name}.service"
            load = "loaded"
            active = service.state.value
            sub = active  # Sub-state, using same as active for simplicity
            description = service.description
            
            results.append(f"{name:<23} {load:<6} {active:<8} {sub:<7} {description}")
        
        results.append("")
        results.append(f"{len(services)} loaded units listed.")
        
        return "\n".join(results)
    
    @staticmethod
    def _systemctl_list_unit_files(options):
        """List available service files"""
        services = ServiceManager.list_services()
        
        if not services:
            return "No service files found"
        
        results = ["UNIT FILE             STATE"]
        
        for service in services:
            name = f"{service.name}.service"
            state = "enabled" if service.restart == ServiceRestartPolicy.ALWAYS else "disabled"
            
            results.append(f"{name:<21} {state}")
        
        results.append("")
        results.append(f"{len(services)} unit files listed.")
        
        return "\n".join(results)
    
    @staticmethod
    def _systemctl_daemon_reload(options):
        """Reload service manager configuration"""
        # Reload services from file
        service_dir = os.path.join(os.path.expanduser('~'), '.kos', 'services')
        service_db = os.path.join(service_dir, 'services.json')
        
        if os.path.exists(service_db):
            success, message = ServiceManager.load_services(service_db)
            if not success:
                return f"Failed to reload service configuration: {message}"
        
        return "Service manager configuration reloaded"
    
    @staticmethod
    def _systemctl_cat(options):
        """Show service file content"""
        if not options:
            return "systemctl cat: no services specified"
        
        results = []
        for service_name in options:
            service = ServiceManager.get_service(service_name)
            
            if not service:
                results.append(f"No files found for {service_name}.service")
                continue
            
            # Format service as a systemd unit file
            service_file = [
                f"# {service_name}.service",
                "[Unit]",
                f"Description={service.description}"
            ]
            
            if service.requires:
                service_file.append(f"Requires={', '.join([f'{req}.service' for req in service.requires])}")
            
            if service.wants:
                service_file.append(f"Wants={', '.join([f'{want}.service' for want in service.wants])}")
            
            if service.after:
                service_file.append(f"After={', '.join([f'{dep}.service' for dep in service.after])}")
            
            if service.before:
                service_file.append(f"Before={', '.join([f'{dep}.service' for dep in service.before])}")
            
            service_file.append("")
            service_file.append("[Service]")
            service_file.append(f"Type={service.type.value}")
            
            if service.working_dir:
                service_file.append(f"WorkingDirectory={service.working_dir}")
            
            if service.command:
                service_file.append(f"ExecStart={service.command}")
            
            if service.restart != ServiceRestartPolicy.NO:
                service_file.append(f"Restart={service.restart.value}")
                service_file.append(f"RestartSec={service.restart_sec}")
            
            if service.user:
                service_file.append(f"User={service.user}")
            
            if service.group:
                service_file.append(f"Group={service.group}")
            
            for key, value in service.environment.items():
                service_file.append(f"Environment={key}={value}")
            
            service_file.append("")
            service_file.append("[Install]")
            service_file.append("WantedBy=multi-user.target")
            
            results.append("\n".join(service_file))
        
        return "\n\n".join(results)
    
    @staticmethod
    def _service_start(service_name, options):
        """Start a service"""
        success, message = ServiceManager.start_service(service_name)
        if not success:
            return f"Failed to start {service_name}: {message}"
        return message
    
    @staticmethod
    def _service_stop(service_name, options):
        """Stop a service"""
        success, message = ServiceManager.stop_service(service_name)
        if not success:
            return f"Failed to stop {service_name}: {message}"
        return message
    
    @staticmethod
    def _service_restart(service_name, options):
        """Restart a service"""
        success, message = ServiceManager.restart_service(service_name)
        if not success:
            return f"Failed to restart {service_name}: {message}"
        return message
    
    @staticmethod
    def _service_reload(service_name, options):
        """Reload a service"""
        success, message = ServiceManager.reload_service(service_name)
        if not success:
            return f"Failed to reload {service_name}: {message}"
        return message
    
    @staticmethod
    def _service_status(service_name, options):
        """Check service status"""
        success, message, status = ServiceManager.status_service(service_name)
        
        if not success:
            return f"{service_name}: {message}"
        
        state = status.get("state", "unknown")
        pid = status.get("pid", "n/a")
        
        if state == "active":
            return f"{service_name} (pid {pid}) is running..."
        else:
            return f"{service_name} is {state}"

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("systemctl", ServiceUtilities.do_systemctl)
    shell.register_command("service", ServiceUtilities.do_service)

"""
Service Monitoring Utilities for KOS Shell

This module provides commands to interact with the KOS service monitoring system,
allowing users to view performance metrics and service health status.
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
from kos.services import ServiceManager, ServiceState
from kos.advlayer.service_monitor import get_instance as get_service_monitor
from kos.advlayer.system_metrics import SystemMetrics

# Set up logging
logger = logging.getLogger('KOS.shell.commands.service_monitor_utils')

class ServiceMonitorUtilities:
    """Service monitoring commands for KOS shell"""
    
    @staticmethod
    def do_svcmon(fs, cwd, arg):
        """
        Monitor and manage KOS service performance
        
        Usage: svcmon COMMAND [options]
        
        Commands:
          start [interval]        Start service monitoring (interval in seconds, default: 10)
          stop                    Stop service monitoring
          status [SERVICE...]     Show monitoring status for services
          metrics [SERVICE...]    Show performance metrics for services
          health [SERVICE...]     Show health status for services
          alerts [SERVICE...]     Show recent alerts for services
          thresholds [options]    View or set alert thresholds
          register SERVICE        Register a service for monitoring
          unregister SERVICE      Unregister a service from monitoring
        """
        args = shlex.split(arg)
        
        if not args:
            return ServiceMonitorUtilities.do_svcmon.__doc__
        
        command = args[0]
        options = args[1:]
        
        # Process commands
        if command == "start":
            return ServiceMonitorUtilities._svcmon_start(options)
        elif command == "stop":
            return ServiceMonitorUtilities._svcmon_stop(options)
        elif command == "status":
            return ServiceMonitorUtilities._svcmon_status(options)
        elif command == "metrics":
            return ServiceMonitorUtilities._svcmon_metrics(options)
        elif command == "health":
            return ServiceMonitorUtilities._svcmon_health(options)
        elif command == "alerts":
            return ServiceMonitorUtilities._svcmon_alerts(options)
        elif command == "thresholds":
            return ServiceMonitorUtilities._svcmon_thresholds(options)
        elif command == "register":
            return ServiceMonitorUtilities._svcmon_register(options)
        elif command == "unregister":
            return ServiceMonitorUtilities._svcmon_unregister(options)
        else:
            return f"svcmon: unknown command '{command}'"
    
    @staticmethod
    def _svcmon_start(options):
        """Start service monitoring"""
        # Get monitoring interval
        interval = 10
        if options and options[0].isdigit():
            interval = int(options[0])
        
        # Get service monitor
        from kos.advlayer import system_metrics
        system_metrics_instance = system_metrics.get_instance()
        service_monitor = get_service_monitor(system_metrics_instance)
        
        # Start monitoring
        if service_monitor.start_monitoring(monitor_interval=interval):
            return f"Service monitoring started (interval: {interval}s)"
        else:
            return "Failed to start service monitoring"
    
    @staticmethod
    def _svcmon_stop(options):
        """Stop service monitoring"""
        # Get service monitor
        service_monitor = get_service_monitor()
        
        # Stop monitoring
        if service_monitor.stop_monitoring():
            return "Service monitoring stopped"
        else:
            return "Failed to stop service monitoring"
    
    @staticmethod
    def _svcmon_status(options):
        """Show monitoring status for services"""
        # Get service monitor
        service_monitor = get_service_monitor()
        
        # Check if monitoring is active
        is_monitoring = hasattr(service_monitor, 'monitoring') and service_monitor.monitoring
        
        # Get service metrics
        if options:
            # Show specific services
            result = [f"Service monitoring: {'ACTIVE' if is_monitoring else 'INACTIVE'}\n"]
            
            for service_name in options:
                # Find service ID
                service = None
                for s in ServiceManager.list_services():
                    if s.name == service_name or s.id == service_name:
                        service = s
                        break
                
                if not service:
                    result.append(f"Service not found: {service_name}")
                    continue
                
                # Get metrics
                metrics = service_monitor.get_service_metrics(service.id)
                
                if not metrics:
                    result.append(f"Service not monitored: {service_name}")
                    continue
                
                # Format status
                status = metrics.get("current_status", "unknown")
                uptime = metrics.get("uptime_percentage", 0)
                restarts = metrics.get("restart_count_24h", 0)
                
                result.append(f"Service: {service.name} ({service.id})")
                result.append(f"  Status: {status}")
                result.append(f"  Uptime: {uptime:.1f}% (24h)")
                result.append(f"  Restarts: {restarts} (24h)")
                result.append("")
            
            return "\n".join(result)
        else:
            # Show all services
            all_metrics = service_monitor.get_all_service_metrics()
            
            if not all_metrics:
                return f"Service monitoring: {'ACTIVE' if is_monitoring else 'INACTIVE'}\nNo services are being monitored"
            
            result = [
                f"Service monitoring: {'ACTIVE' if is_monitoring else 'INACTIVE'}",
                "",
                "SERVICE                STATUS      UPTIME    RESTARTS  CPU     MEM"
            ]
            
            for service_id, metrics in all_metrics.items():
                name = metrics.get("name", "unknown")
                status = metrics.get("current_status", "unknown")
                uptime = metrics.get("uptime_percentage", 0)
                restarts = metrics.get("restart_count_24h", 0)
                cpu = metrics.get("current_cpu_usage", 0)
                mem = metrics.get("current_memory_usage", 0)
                
                result.append(f"{name:<22} {status:<11} {uptime:>5.1f}%   {restarts:>5}     {cpu:>5.1f}%  {mem:>5.1f}%")
            
            return "\n".join(result)
    
    @staticmethod
    def _svcmon_metrics(options):
        """Show performance metrics for services"""
        # Get service monitor
        service_monitor = get_service_monitor()
        
        if options:
            # Show specific services
            result = []
            
            for service_name in options:
                # Find service ID
                service = None
                for s in ServiceManager.list_services():
                    if s.name == service_name or s.id == service_name:
                        service = s
                        break
                
                if not service:
                    result.append(f"Service not found: {service_name}")
                    continue
                
                # Get metrics
                metrics = service_monitor.get_service_metrics(service.id)
                
                if not metrics:
                    result.append(f"Service not monitored: {service_name}")
                    continue
                
                # Format detailed metrics
                result.append(f"Performance metrics for {service.name} ({service.id}):")
                result.append(f"  Status: {metrics.get('current_status', 'unknown')}")
                result.append(f"  Uptime: {metrics.get('uptime_percentage', 0):.1f}% (24h)")
                result.append(f"  Restarts: {metrics.get('restart_count_24h', 0)} (24h)")
                result.append(f"  CPU usage: {metrics.get('current_cpu_usage', 0):.1f}%")
                result.append(f"  Memory usage: {metrics.get('current_memory_usage', 0):.1f}%")
                
                if metrics.get('average_response_time') is not None:
                    result.append(f"  Response time: {metrics.get('average_response_time', 0):.1f}ms (1h average)")
                
                # Status history
                status_history = metrics.get('status_history', [])
                if status_history:
                    result.append("\n  Status history:")
                    for ts, status in status_history[-5:]:  # Last 5 status changes
                        dt = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                        result.append(f"    {dt}: {status}")
                
                # Restart history
                restart_history = metrics.get('restart_history', [])
                if restart_history:
                    result.append("\n  Restart history:")
                    for ts, exit_code in restart_history[-5:]:  # Last 5 restarts
                        dt = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                        exit_str = f"exit code {exit_code}" if exit_code is not None else "unknown reason"
                        result.append(f"    {dt}: {exit_str}")
                
                result.append("")
            
            return "\n".join(result)
        else:
            # Show all services summary
            all_metrics = service_monitor.get_all_service_metrics()
            
            if not all_metrics:
                return "No services are being monitored"
            
            result = ["SERVICE PERFORMANCE METRICS", ""]
            
            for service_id, metrics in all_metrics.items():
                name = metrics.get("name", "unknown")
                cpu = metrics.get("current_cpu_usage", 0)
                mem = metrics.get("current_memory_usage", 0)
                uptime = metrics.get("uptime_percentage", 0)
                restarts = metrics.get("restart_count_24h", 0)
                
                result.append(f"Service: {name}")
                result.append(f"  CPU: {cpu:.1f}%")
                result.append(f"  Memory: {mem:.1f}%")
                result.append(f"  Uptime: {uptime:.1f}% (24h)")
                result.append(f"  Restarts: {restarts} (24h)")
                
                if metrics.get('average_response_time') is not None:
                    result.append(f"  Response time: {metrics.get('average_response_time', 0):.1f}ms (1h average)")
                
                result.append("")
            
            return "\n".join(result)
    
    @staticmethod
    def _svcmon_health(options):
        """Show health status for services"""
        # Get service monitor
        service_monitor = get_service_monitor()
        
        if options:
            # Show specific services
            result = []
            
            for service_name in options:
                # Find service ID
                service = None
                for s in ServiceManager.list_services():
                    if s.name == service_name or s.id == service_name:
                        service = s
                        break
                
                if not service:
                    result.append(f"Service not found: {service_name}")
                    continue
                
                # Get metrics
                metrics = service_monitor.get_service_metrics(service.id)
                
                if not metrics:
                    result.append(f"Service not monitored: {service_name}")
                    continue
                
                # Format health status
                result.append(f"Health status for {service.name} ({service.id}):")
                
                health_status = metrics.get('health_status', [])
                if health_status:
                    latest_health = health_status[-1]
                    health_time = datetime.datetime.fromtimestamp(latest_health[0]).strftime('%Y-%m-%d %H:%M:%S')
                    health_state = latest_health[1]
                    
                    result.append(f"  Current health: {health_state} (as of {health_time})")
                    
                    if len(health_status) > 1:
                        result.append("\n  Health history:")
                        for ts, status in health_status[-5:]:  # Last 5 health checks
                            dt = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                            result.append(f"    {dt}: {status}")
                else:
                    result.append("  No health checks recorded")
                
                result.append("")
            
            return "\n".join(result)
        else:
            # Show all services health summary
            all_metrics = service_monitor.get_all_service_metrics()
            
            if not all_metrics:
                return "No services are being monitored"
            
            result = ["SERVICE HEALTH STATUS", ""]
            result.append("SERVICE                HEALTH      LAST CHECK            RESPONSE TIME")
            
            for service_id, metrics in all_metrics.items():
                name = metrics.get("name", "unknown")
                
                health_status = metrics.get('health_status', [])
                if health_status:
                    latest_health = health_status[-1]
                    health_time = datetime.datetime.fromtimestamp(latest_health[0]).strftime('%Y-%m-%d %H:%M:%S')
                    health_state = latest_health[1]
                    response_time = metrics.get('average_response_time', 0)
                    
                    result.append(f"{name:<22} {health_state:<11} {health_time}  {response_time:>8.1f}ms")
                else:
                    result.append(f"{name:<22} {'No checks':.<11} {'N/A':.<21} {'N/A':>8}")
            
            return "\n".join(result)
    
    @staticmethod
    def _svcmon_alerts(options):
        """Show recent alerts for services"""
        # Note: In a real implementation, we would store alerts in a database
        # For this example, we'll return a placeholder message
        return "Alert history not available. Alerts are logged to the KOS log file."
    
    @staticmethod
    def _svcmon_thresholds(options):
        """View or set alert thresholds"""
        # Get service monitor
        service_monitor = get_service_monitor()
        
        # Parse options
        cpu = None
        memory = None
        restarts = None
        response_time = None
        
        i = 0
        while i < len(options):
            if options[i] == "--cpu":
                if i + 1 < len(options):
                    try:
                        cpu = float(options[i+1])
                        i += 2
                    except ValueError:
                        return f"Invalid CPU threshold: {options[i+1]}"
                else:
                    return "svcmon thresholds: option requires an argument -- '--cpu'"
            elif options[i] == "--memory":
                if i + 1 < len(options):
                    try:
                        memory = float(options[i+1])
                        i += 2
                    except ValueError:
                        return f"Invalid memory threshold: {options[i+1]}"
                else:
                    return "svcmon thresholds: option requires an argument -- '--memory'"
            elif options[i] == "--restarts":
                if i + 1 < len(options):
                    try:
                        restarts = int(options[i+1])
                        i += 2
                    except ValueError:
                        return f"Invalid restarts threshold: {options[i+1]}"
                else:
                    return "svcmon thresholds: option requires an argument -- '--restarts'"
            elif options[i] == "--response-time":
                if i + 1 < len(options):
                    try:
                        response_time = float(options[i+1])
                        i += 2
                    except ValueError:
                        return f"Invalid response time threshold: {options[i+1]}"
                else:
                    return "svcmon thresholds: option requires an argument -- '--response-time'"
            else:
                i += 1
        
        # Update thresholds if provided
        if cpu is not None or memory is not None or restarts is not None or response_time is not None:
            service_monitor.set_alert_thresholds(cpu, memory, restarts, response_time)
            
            # Show updated thresholds
            result = ["Alert thresholds updated:"]
        else:
            # Show current thresholds
            result = ["Current alert thresholds:"]
        
        # Display current thresholds
        result.append(f"  CPU usage: {service_monitor.cpu_threshold}%")
        result.append(f"  Memory usage: {service_monitor.memory_threshold}%")
        result.append(f"  Restarts: {service_monitor.restart_threshold} in 1 hour")
        result.append(f"  Response time: {service_monitor.response_time_threshold}ms")
        
        return "\n".join(result)
    
    @staticmethod
    def _svcmon_register(options):
        """Register a service for monitoring"""
        if not options:
            return "svcmon register: service name or ID is required"
        
        service_name = options[0]
        
        # Find service
        service = None
        for s in ServiceManager.list_services():
            if s.name == service_name or s.id == service_name:
                service = s
                break
        
        if not service:
            return f"Service not found: {service_name}"
        
        # Get service monitor
        service_monitor = get_service_monitor()
        
        # Register service
        if service_monitor.register_service(service.id, service.name):
            return f"Service registered for monitoring: {service.name} ({service.id})"
        else:
            return f"Failed to register service: {service.name}"
    
    @staticmethod
    def _svcmon_unregister(options):
        """Unregister a service from monitoring"""
        if not options:
            return "svcmon unregister: service name or ID is required"
        
        service_name = options[0]
        
        # Find service
        service = None
        for s in ServiceManager.list_services():
            if s.name == service_name or s.id == service_name:
                service = s
                break
        
        if not service:
            return f"Service not found: {service_name}"
        
        # Get service monitor
        service_monitor = get_service_monitor()
        
        # Unregister service
        if service_monitor.unregister_service(service.id):
            return f"Service unregistered from monitoring: {service.name} ({service.id})"
        else:
            return f"Failed to unregister service: {service.name}"

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("svcmon", ServiceMonitorUtilities.do_svcmon)

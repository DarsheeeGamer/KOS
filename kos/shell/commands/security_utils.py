"""
Central Security Utilities for KOS Shell

This module provides a unified command interface for managing all KOS security features,
including FIM, IDS, Network Monitor, Audit, and Security Policy systems.
"""

import os
import sys
import logging
import shlex
import json
import time
from typing import Dict, List, Any, Optional, Tuple

# Import KOS security components
from kos.security.security_manager import SecurityManager
from kos.security.fim import FIMManager
from kos.security.ids import IDSManager
from kos.security.network_monitor import NetworkMonitor
from kos.security.audit import AuditSystem
from kos.security.policy import PolicyManager
from kos.security.acl import ACLManager
from kos.security.mac import MACManager
from kos.security.users import UserManager
from kos.security.auth import AuthManager

# Set up logging
logger = logging.getLogger('KOS.shell.commands.security_utils')

class SecurityUtilities:
    """Central Security command for KOS shell"""
    
    @staticmethod
    def do_security(fs, cwd, arg):
        """
        Manage KOS Security Systems
        
        Usage: security COMMAND [options]
        
        Commands:
          status                         Show security status across all components
          enable [component]             Enable security component(s)
          disable [component]            Disable security component(s)
          policy SUBCOMMAND              Manage security policies
          alerts [options]               View security alerts
          fim SUBCOMMAND                 File Integrity Monitoring
          ids SUBCOMMAND                 Intrusion Detection System
          netmon SUBCOMMAND              Network Security Monitor
          audit SUBCOMMAND               Security Audit System
          acl SUBCOMMAND                 Access Control Lists
          mac SUBCOMMAND                 Mandatory Access Control
          users SUBCOMMAND               User and Group Management
          auth SUBCOMMAND                Authentication Management
        
        Components:
          all                            All security components
          fim                            File Integrity Monitoring
          ids                            Intrusion Detection System
          netmon                         Network Security Monitor
          audit                          Security Audit System
          acl                            Access Control Lists
          mac                            Mandatory Access Control
        """
        args = shlex.split(arg)
        
        if not args:
            return SecurityUtilities.do_security.__doc__
        
        command = args[0]
        options = args[1:]
        
        # Process commands
        if command == "status":
            return SecurityUtilities._security_status(fs, cwd, options)
        elif command == "enable":
            return SecurityUtilities._security_enable(fs, cwd, options)
        elif command == "disable":
            return SecurityUtilities._security_disable(fs, cwd, options)
        elif command == "policy":
            return SecurityUtilities._security_policy(fs, cwd, options)
        elif command == "alerts":
            return SecurityUtilities._security_alerts(fs, cwd, options)
        elif command == "fim":
            # Delegate to FIM command
            from kos.shell.commands.fim_utils import FIMUtilities
            return FIMUtilities.do_fim(fs, cwd, " ".join(options))
        elif command == "ids":
            # Delegate to IDS command
            from kos.shell.commands.ids_utils import IDSUtilities
            return IDSUtilities.do_ids(fs, cwd, " ".join(options))
        elif command == "netmon":
            # Delegate to Network Monitor command
            from kos.shell.commands.network_monitor_utils import NetworkMonitorUtilities
            return NetworkMonitorUtilities.do_netmon(fs, cwd, " ".join(options))
        elif command == "audit":
            # Delegate to Audit command
            from kos.shell.commands.audit_utils import AuditUtilities
            return AuditUtilities.do_audit(fs, cwd, " ".join(options))
        elif command == "acl":
            # Delegate to ACL command
            from kos.shell.commands.acl_utils import ACLUtilities
            return ACLUtilities.do_acl(fs, cwd, " ".join(options))
        elif command == "mac":
            # Delegate to MAC command
            from kos.shell.commands.mac_utils import MACUtilities
            return MACUtilities.do_mac(fs, cwd, " ".join(options))
        elif command == "users":
            # Delegate to Users command
            from kos.shell.commands.user_utils import UserUtilities
            return UserUtilities.do_user(fs, cwd, " ".join(options))
        elif command == "auth":
            # Delegate to Auth command
            from kos.shell.commands.auth_utils import AuthUtilities
            return AuthUtilities.do_auth(fs, cwd, " ".join(options))
        else:
            return f"security: unknown command: {command}"
    
    @staticmethod
    def _security_status(fs, cwd, options):
        """Show security status across all components"""
        # Get security status
        status = SecurityManager().get_security_status()
        
        # Get active policy
        active_policy = PolicyManager.get_active_policy()
        
        # Format output
        output = ["KOS Security Status:"]
        output.append("")
        
        # Active policy
        output.append("Security Policy:")
        if active_policy:
            output.append(f"  Active Policy: {active_policy.name}")
            output.append(f"  Version: {active_policy.version}")
            output.append(f"  Description: {active_policy.description}")
        else:
            output.append("  No active security policy")
        
        output.append("")
        
        # File Integrity Monitoring
        output.append("File Integrity Monitoring (FIM):")
        output.append(f"  Enabled: {'Yes' if status['fim']['enabled'] else 'No'}")
        output.append(f"  Monitored Files: {status['fim']['monitored_files']}")
        output.append(f"  Check Interval: {status['fim']['check_interval']} seconds")
        output.append(f"  Hash Algorithm: {status['fim']['hash_algorithm']}")
        output.append(f"  Alerts: {status['fim']['alerts']}")
        
        output.append("")
        
        # Intrusion Detection System
        output.append("Intrusion Detection System (IDS):")
        output.append(f"  Enabled: {'Yes' if status['ids']['enabled'] else 'No'}")
        output.append(f"  Rules: {status['ids']['rules_count']}")
        output.append(f"  Events: {status['ids']['events_count']}")
        output.append(f"  Scan Interval: {status['ids']['scan_interval']} seconds")
        
        output.append("")
        
        # Network Monitor
        output.append("Network Security Monitor:")
        output.append(f"  Enabled: {'Yes' if status['network_monitor']['enabled'] else 'No'}")
        output.append(f"  Monitored Ports: {', '.join(map(str, status['network_monitor']['monitored_ports']))}")
        output.append(f"  Blacklist: {status['network_monitor']['blacklist_count']} entries")
        output.append(f"  Whitelist: {status['network_monitor']['whitelist_count']} entries")
        output.append(f"  Active Connections: {status['network_monitor']['connections_count']}")
        
        output.append("")
        
        # Audit System
        output.append("Security Audit System:")
        output.append(f"  Enabled: {'Yes' if status['audit']['enabled'] else 'No'}")
        output.append(f"  Hash Chain: {'Yes' if status['audit']['hash_chain'] else 'No'}")
        output.append(f"  Synchronous Writes: {'Yes' if status['audit']['sync_write'] else 'No'}")
        output.append(f"  Events: {status['audit']['events_count']}")
        
        return "\n".join(output)
    
    @staticmethod
    def _security_enable(fs, cwd, options):
        """Enable security component(s)"""
        if not options:
            return "security enable: component required"
        
        component = options[0]
        
        if component == "all":
            # Enable all components
            results = SecurityManager().enable_all_components()
            
            # Format output
            output = ["Enabled security components:"]
            
            for comp, (success, message) in results.items():
                if success:
                    output.append(f"  {comp}: {message}")
                else:
                    output.append(f"  {comp}: FAILED - {message}")
            
            # Add audit event
            AuditSystem.add_event(
                category='security_config',
                event_type='security_components_enabled',
                user='console',
                source='security_manager',
                details={'components': list(results.keys())},
                severity=3,
                outcome='success'
            )
            
            return "\n".join(output)
        elif component == "fim":
            # Enable FIM
            FIMManager.enable()
            
            # Add audit event
            AuditSystem.add_event(
                category='security_config',
                event_type='fim_enabled',
                user='console',
                source='security_manager',
                details={},
                severity=3,
                outcome='success'
            )
            
            return "File Integrity Monitoring enabled"
        elif component == "ids":
            # Enable IDS
            IDSManager.enable()
            
            # Add audit event
            AuditSystem.add_event(
                category='security_config',
                event_type='ids_enabled',
                user='console',
                source='security_manager',
                details={},
                severity=3,
                outcome='success'
            )
            
            return "Intrusion Detection System enabled"
        elif component == "netmon":
            # Enable Network Monitor
            NetworkMonitor.start_monitoring()
            
            # Add audit event
            AuditSystem.add_event(
                category='security_config',
                event_type='network_monitor_enabled',
                user='console',
                source='security_manager',
                details={},
                severity=3,
                outcome='success'
            )
            
            return "Network Security Monitor enabled"
        elif component == "audit":
            # Enable Audit
            AuditSystem.enable()
            
            return "Security Audit System enabled"
        else:
            return f"security enable: unknown component: {component}"
    
    @staticmethod
    def _security_disable(fs, cwd, options):
        """Disable security component(s)"""
        if not options:
            return "security disable: component required"
        
        component = options[0]
        
        if component == "all":
            # Disable all components
            results = SecurityManager().disable_all_components()
            
            # Format output
            output = ["Disabled security components:"]
            
            for comp, (success, message) in results.items():
                if success:
                    output.append(f"  {comp}: {message}")
                else:
                    output.append(f"  {comp}: FAILED - {message}")
            
            # Add audit event
            AuditSystem.add_event(
                category='security_config',
                event_type='security_components_disabled',
                user='console',
                source='security_manager',
                details={'components': list(results.keys())},
                severity=3,
                outcome='success'
            )
            
            return "\n".join(output)
        elif component == "fim":
            # Disable FIM
            FIMManager.disable()
            
            # Add audit event
            AuditSystem.add_event(
                category='security_config',
                event_type='fim_disabled',
                user='console',
                source='security_manager',
                details={},
                severity=3,
                outcome='success'
            )
            
            return "File Integrity Monitoring disabled"
        elif component == "ids":
            # Disable IDS
            IDSManager.disable()
            
            # Add audit event
            AuditSystem.add_event(
                category='security_config',
                event_type='ids_disabled',
                user='console',
                source='security_manager',
                details={},
                severity=3,
                outcome='success'
            )
            
            return "Intrusion Detection System disabled"
        elif component == "netmon":
            # Disable Network Monitor
            NetworkMonitor.stop_monitoring()
            
            # Add audit event
            AuditSystem.add_event(
                category='security_config',
                event_type='network_monitor_disabled',
                user='console',
                source='security_manager',
                details={},
                severity=3,
                outcome='success'
            )
            
            return "Network Security Monitor disabled"
        elif component == "audit":
            # Disable Audit
            AuditSystem.disable()
            
            return "Security Audit System disabled"
        else:
            return f"security disable: unknown component: {component}"
    
    @staticmethod
    def _security_policy(fs, cwd, options):
        """Manage security policies"""
        if not options:
            return "security policy: subcommand required"
        
        subcommand = options[0]
        suboptions = options[1:]
        
        if subcommand == "apply":
            # Apply active policy
            success, message = SecurityManager().apply_active_policy()
            
            return message
        elif subcommand == "status":
            # Get active policy
            active_policy = PolicyManager.get_active_policy()
            
            if not active_policy:
                return "No active security policy"
            
            # Format output
            output = ["Security Policy Status:"]
            output.append("")
            output.append(f"Active Policy: {active_policy.name}")
            output.append(f"Version: {active_policy.version}")
            output.append(f"Description: {active_policy.description}")
            
            return "\n".join(output)
        else:
            # Delegate to policy command
            from kos.shell.commands.policy_utils import PolicyUtilities
            return PolicyUtilities.do_policy(fs, cwd, " ".join(options))
    
    @staticmethod
    def _security_alerts(fs, cwd, options):
        """View security alerts"""
        # Parse options
        limit = 10  # Default limit
        severity = None
        source = None
        
        i = 0
        while i < len(options):
            if options[i] == "--limit":
                if i + 1 < len(options):
                    try:
                        limit = int(options[i+1])
                        i += 2
                    except ValueError:
                        return f"security alerts: invalid limit: {options[i+1]}"
                else:
                    return "security alerts: option requires an argument -- '--limit'"
            elif options[i] == "--severity":
                if i + 1 < len(options):
                    try:
                        severity = int(options[i+1])
                        i += 2
                    except ValueError:
                        return f"security alerts: invalid severity: {options[i+1]}"
                else:
                    return "security alerts: option requires an argument -- '--severity'"
            elif options[i] == "--source":
                if i + 1 < len(options):
                    source = options[i+1]
                    i += 2
                else:
                    return "security alerts: option requires an argument -- '--source'"
            elif options[i] == "--all":
                limit = None
                i += 1
            else:
                return f"security alerts: unknown option: {options[i]}"
        
        # Get alerts from different sources
        alerts = []
        
        # FIM alerts
        if source is None or source == "fim":
            fim_alerts = FIMManager.get_alerts()
            for alert in fim_alerts:
                alerts.append({
                    'timestamp': alert.timestamp,
                    'source': 'fim',
                    'type': 'integrity_violation',
                    'details': {
                        'path': alert.file_path,
                        'expected_hash': alert.expected_hash,
                        'actual_hash': alert.actual_hash
                    },
                    'severity': 8
                })
        
        # IDS alerts
        if source is None or source == "ids":
            ids_events = IDSManager.get_events()
            for event in ids_events:
                severity_map = {
                    'low': 3,
                    'medium': 5,
                    'high': 8,
                    'critical': 10
                }
                alerts.append({
                    'timestamp': event.timestamp,
                    'source': 'ids',
                    'type': event.rule_name,
                    'details': {
                        'data': event.event_data,
                        'rule': event.rule_name
                    },
                    'severity': severity_map.get(event.severity, 5)
                })
        
        # Network Monitor alerts
        if source is None or source == "netmon":
            suspicious_connections = NetworkMonitor.get_suspicious_connections()
            for conn in suspicious_connections:
                alerts.append({
                    'timestamp': conn.timestamp,
                    'source': 'netmon',
                    'type': 'suspicious_connection',
                    'details': {
                        'source_ip': conn.source_ip,
                        'source_port': conn.source_port,
                        'dest_ip': conn.dest_ip,
                        'dest_port': conn.dest_port,
                        'protocol': conn.protocol,
                        'reason': conn.reason
                    },
                    'severity': 7
                })
        
        # Filter by severity
        if severity is not None:
            alerts = [a for a in alerts if a['severity'] >= severity]
        
        # Sort by timestamp (newest first)
        alerts.sort(key=lambda a: a['timestamp'], reverse=True)
        
        # Apply limit
        if limit is not None:
            alerts = alerts[:limit]
        
        if not alerts:
            return "No security alerts found"
        
        # Format output
        output = [f"Security Alerts: {len(alerts)}"]
        output.append("TIME                 SOURCE   TYPE                SEVERITY DETAILS")
        output.append("-" * 100)
        
        for alert in alerts:
            # Format timestamp
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(alert['timestamp']))
            
            # Format details
            details_str = str(alert['details'])
            if len(details_str) > 40:
                details_str = details_str[:37] + "..."
            
            output.append(f"{timestamp} {alert['source']:<8} {alert['type']:<20} {alert['severity']:<8} {details_str}")
        
        return "\n".join(output)


def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("security", SecurityUtilities.do_security)

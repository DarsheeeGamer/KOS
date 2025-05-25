"""
Security Audit Utilities for KOS Shell

This module provides commands for managing the KOS Security Audit system,
allowing users to record, view, and manage security-relevant events.
"""

import os
import sys
import logging
import shlex
import json
import time
from typing import Dict, List, Any, Optional, Tuple

# Import KOS components
from kos.security.audit import AuditSystem, AuditEvent

# Set up logging
logger = logging.getLogger('KOS.shell.commands.audit_utils')

class AuditUtilities:
    """Security Audit commands for KOS shell"""
    
    @staticmethod
    def do_audit(fs, cwd, arg):
        """
        Manage KOS Security Audit System
        
        Usage: audit COMMAND [options]
        
        Commands:
          enable                      Enable audit logging
          disable                     Disable audit logging
          status                      Show audit status
          events [options]            List audit events
          clear                       Clear all events
          verify                      Verify audit log integrity
          config set OPTION VALUE     Set configuration option
          config show                 Show current configuration
          export FILE [format]        Export audit events to file
          import FILE                 Import audit events from file
          log EVENT [options]         Log a manual audit event
        """
        args = shlex.split(arg)
        
        if not args:
            return AuditUtilities.do_audit.__doc__
        
        command = args[0]
        options = args[1:]
        
        # Process commands
        if command == "enable":
            return AuditUtilities._audit_enable(fs, cwd, options)
        elif command == "disable":
            return AuditUtilities._audit_disable(fs, cwd, options)
        elif command == "status":
            return AuditUtilities._audit_status(fs, cwd, options)
        elif command == "events":
            return AuditUtilities._audit_events(fs, cwd, options)
        elif command == "clear":
            return AuditUtilities._audit_clear(fs, cwd, options)
        elif command == "verify":
            return AuditUtilities._audit_verify(fs, cwd, options)
        elif command == "config":
            if not options:
                return "audit config: subcommand required (set or show)"
            
            subcommand = options[0]
            suboptions = options[1:]
            
            if subcommand == "set":
                return AuditUtilities._audit_config_set(fs, cwd, suboptions)
            elif subcommand == "show":
                return AuditUtilities._audit_config_show(fs, cwd, suboptions)
            else:
                return f"audit config: unknown subcommand: {subcommand}"
        elif command == "export":
            return AuditUtilities._audit_export(fs, cwd, options)
        elif command == "import":
            return AuditUtilities._audit_import(fs, cwd, options)
        elif command == "log":
            return AuditUtilities._audit_log(fs, cwd, options)
        else:
            return f"audit: unknown command: {command}"
    
    @staticmethod
    def _audit_enable(fs, cwd, options):
        """Enable audit logging"""
        success, message = AuditSystem.enable()
        return message
    
    @staticmethod
    def _audit_disable(fs, cwd, options):
        """Disable audit logging"""
        success, message = AuditSystem.disable()
        return message
    
    @staticmethod
    def _audit_status(fs, cwd, options):
        """Show audit status"""
        # Get audit status
        enabled = AuditSystem._audit_config['enabled']
        log_file = AuditSystem._audit_config['log_file']
        json_file = AuditSystem._audit_config['json_file']
        rotation_size = AuditSystem._audit_config['rotation_size']
        max_log_files = AuditSystem._audit_config['max_log_files']
        hash_chain = AuditSystem._audit_config['hash_chain']
        sync_write = AuditSystem._audit_config['sync_write']
        event_categories = AuditSystem._audit_config['event_categories']
        
        # Count events
        events_count = len(AuditSystem._audit_events)
        
        # Format output
        output = ["Security Audit Status:"]
        output.append(f"  Enabled: {'Yes' if enabled else 'No'}")
        output.append(f"  Log File: {log_file}")
        output.append(f"  JSON File: {json_file}")
        output.append(f"  Rotation Size: {rotation_size} bytes")
        output.append(f"  Maximum Log Files: {max_log_files}")
        output.append(f"  Hash Chain: {'Enabled' if hash_chain else 'Disabled'}")
        output.append(f"  Synchronous Writes: {'Enabled' if sync_write else 'Disabled'}")
        output.append(f"  Event Count: {events_count}")
        output.append("  Event Categories:")
        for category in event_categories:
            output.append(f"    - {category}")
        
        # Verify integrity
        integrity_intact, error_message = AuditSystem.verify_integrity()
        if integrity_intact:
            output.append("  Integrity: OK")
        else:
            output.append(f"  Integrity: FAILED - {error_message}")
        
        return "\n".join(output)
    
    @staticmethod
    def _audit_events(fs, cwd, options):
        """List audit events"""
        # Parse options
        limit = 10  # Default limit
        start_time = None
        end_time = None
        category = None
        event_type = None
        user = None
        source = None
        min_severity = None
        outcome = None
        
        i = 0
        while i < len(options):
            if options[i] == "--limit":
                if i + 1 < len(options):
                    try:
                        limit = int(options[i+1])
                        i += 2
                    except ValueError:
                        return f"audit events: invalid limit: {options[i+1]}"
                else:
                    return "audit events: option requires an argument -- '--limit'"
            elif options[i] == "--category":
                if i + 1 < len(options):
                    category = options[i+1]
                    i += 2
                else:
                    return "audit events: option requires an argument -- '--category'"
            elif options[i] == "--type":
                if i + 1 < len(options):
                    event_type = options[i+1]
                    i += 2
                else:
                    return "audit events: option requires an argument -- '--type'"
            elif options[i] == "--user":
                if i + 1 < len(options):
                    user = options[i+1]
                    i += 2
                else:
                    return "audit events: option requires an argument -- '--user'"
            elif options[i] == "--source":
                if i + 1 < len(options):
                    source = options[i+1]
                    i += 2
                else:
                    return "audit events: option requires an argument -- '--source'"
            elif options[i] == "--min-severity":
                if i + 1 < len(options):
                    try:
                        min_severity = int(options[i+1])
                        i += 2
                    except ValueError:
                        return f"audit events: invalid severity: {options[i+1]}"
                else:
                    return "audit events: option requires an argument -- '--min-severity'"
            elif options[i] == "--outcome":
                if i + 1 < len(options):
                    outcome = options[i+1]
                    i += 2
                else:
                    return "audit events: option requires an argument -- '--outcome'"
            elif options[i] == "--all":
                limit = None
                i += 1
            else:
                return f"audit events: unknown option: {options[i]}"
        
        # Get events
        events = AuditSystem.get_events(
            start_time=start_time,
            end_time=end_time,
            category=category,
            event_type=event_type,
            user=user,
            source=source,
            min_severity=min_severity,
            outcome=outcome,
            limit=limit
        )
        
        if not events:
            return "No audit events found"
        
        # Format output
        output = [f"Audit Events: {len(events)}"]
        output.append("TIME                 CATEGORY    TYPE          USER      SOURCE    SEV OUTCOME  DETAILS")
        output.append("-" * 100)
        
        for event in events:
            # Format timestamp
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(event.timestamp))
            
            # Format details
            details_str = str(event.details)
            if len(details_str) > 30:
                details_str = details_str[:27] + "..."
            
            output.append(f"{timestamp} {event.category:<10} {event.event_type:<12} {event.user:<9} {event.source:<9} {event.severity:<3} {event.outcome:<8} {details_str}")
        
        return "\n".join(output)
    
    @staticmethod
    def _audit_clear(fs, cwd, options):
        """Clear all events"""
        success, message = AuditSystem.clear_events()
        return message
    
    @staticmethod
    def _audit_verify(fs, cwd, options):
        """Verify audit log integrity"""
        integrity_intact, error_message = AuditSystem.verify_integrity()
        
        if integrity_intact:
            return "Audit log integrity verification: PASSED"
        else:
            return f"Audit log integrity verification: FAILED - {error_message}"
    
    @staticmethod
    def _audit_config_set(fs, cwd, options):
        """Set configuration option"""
        if len(options) < 2:
            return "audit config set: option and value required"
        
        option = options[0]
        value = options[1]
        
        if option == "log_file":
            success, message = AuditSystem.set_log_file(value)
            return message
        elif option == "json_file":
            success, message = AuditSystem.set_json_file(value)
            return message
        elif option == "rotation_size":
            try:
                size = int(value)
                success, message = AuditSystem.set_rotation_size(size)
                return message
            except ValueError:
                return f"audit config set: invalid rotation size: {value}"
        elif option == "max_log_files":
            try:
                max_files = int(value)
                success, message = AuditSystem.set_max_log_files(max_files)
                return message
            except ValueError:
                return f"audit config set: invalid max log files: {value}"
        elif option == "hash_chain":
            if value.lower() in ["yes", "true", "1", "on"]:
                success, message = AuditSystem.set_hash_chain(True)
                return message
            elif value.lower() in ["no", "false", "0", "off"]:
                success, message = AuditSystem.set_hash_chain(False)
                return message
            else:
                return f"audit config set: invalid value for hash_chain: {value}"
        elif option == "sync_write":
            if value.lower() in ["yes", "true", "1", "on"]:
                success, message = AuditSystem.set_sync_write(True)
                return message
            elif value.lower() in ["no", "false", "0", "off"]:
                success, message = AuditSystem.set_sync_write(False)
                return message
            else:
                return f"audit config set: invalid value for sync_write: {value}"
        else:
            return f"audit config set: unknown option: {option}"
    
    @staticmethod
    def _audit_config_show(fs, cwd, options):
        """Show current configuration"""
        config = AuditSystem._audit_config
        
        # Format output
        output = ["Audit Configuration:"]
        
        for key, value in sorted(config.items()):
            if key == "event_categories":
                output.append(f"  {key}: {', '.join(value)}")
            else:
                output.append(f"  {key}: {value}")
        
        return "\n".join(output)
    
    @staticmethod
    def _audit_export(fs, cwd, options):
        """Export audit events to file"""
        if not options:
            return "audit export: file path required"
        
        export_file = options[0]
        
        # Resolve relative path
        if not os.path.isabs(export_file):
            export_file = os.path.join(cwd, export_file)
        
        # Get format
        format = "json"
        if len(options) > 1:
            format = options[1]
        
        # Export events
        success, message = AuditSystem.export_events(export_file, format)
        
        return message
    
    @staticmethod
    def _audit_import(fs, cwd, options):
        """Import audit events from file"""
        if not options:
            return "audit import: file path required"
        
        import_file = options[0]
        
        # Resolve relative path
        if not os.path.isabs(import_file):
            import_file = os.path.join(cwd, import_file)
        
        # Import events
        success, message = AuditSystem.import_events(import_file)
        
        return message
    
    @staticmethod
    def _audit_log(fs, cwd, options):
        """Log a manual audit event"""
        if not options:
            return "audit log: event type required"
        
        event_type = options[0]
        
        # Parse options
        category = "user"
        user = "console"
        source = "manual"
        details = {}
        severity = 1
        outcome = "success"
        
        i = 1
        while i < len(options):
            if options[i] == "--category":
                if i + 1 < len(options):
                    category = options[i+1]
                    i += 2
                else:
                    return "audit log: option requires an argument -- '--category'"
            elif options[i] == "--user":
                if i + 1 < len(options):
                    user = options[i+1]
                    i += 2
                else:
                    return "audit log: option requires an argument -- '--user'"
            elif options[i] == "--source":
                if i + 1 < len(options):
                    source = options[i+1]
                    i += 2
                else:
                    return "audit log: option requires an argument -- '--source'"
            elif options[i] == "--message":
                if i + 1 < len(options):
                    details["message"] = options[i+1]
                    i += 2
                else:
                    return "audit log: option requires an argument -- '--message'"
            elif options[i] == "--severity":
                if i + 1 < len(options):
                    try:
                        severity = int(options[i+1])
                        i += 2
                    except ValueError:
                        return f"audit log: invalid severity: {options[i+1]}"
                else:
                    return "audit log: option requires an argument -- '--severity'"
            elif options[i] == "--outcome":
                if i + 1 < len(options):
                    outcome = options[i+1]
                    i += 2
                else:
                    return "audit log: option requires an argument -- '--outcome'"
            elif options[i].startswith("--"):
                return f"audit log: unknown option: {options[i]}"
            else:
                # Add any remaining arguments as details
                if "message" not in details:
                    details["message"] = " ".join(options[i:])
                break
        
        # Add event
        event = AuditSystem.add_event(
            category=category,
            event_type=event_type,
            user=user,
            source=source,
            details=details,
            severity=severity,
            outcome=outcome
        )
        
        return f"Audit event logged: {event.event_type} (ID: {event.event_hash[:8]})"

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("audit", AuditUtilities.do_audit)

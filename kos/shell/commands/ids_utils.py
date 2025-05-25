"""
Intrusion Detection System Utilities for KOS Shell

This module provides commands for managing the KOS IDS system,
allowing users to detect and respond to security threats.
"""

import os
import sys
import logging
import shlex
import json
import time
from typing import Dict, List, Any, Optional, Tuple

# Import KOS components
from kos.security.ids import IDSManager, IDSEvent, IDSRule

# Set up logging
logger = logging.getLogger('KOS.shell.commands.ids_utils')

class IDSUtilities:
    """Intrusion Detection System commands for KOS shell"""
    
    @staticmethod
    def do_ids(fs, cwd, arg):
        """
        Manage KOS Intrusion Detection System
        
        Usage: ids COMMAND [options]
        
        Commands:
          start                       Start IDS monitoring
          stop                        Stop IDS monitoring
          status                      Show IDS status
          events [options]            List IDS events
          rules [options]             List IDS rules
          rule add [options]          Add a rule
          rule remove RULE_ID         Remove a rule
          rule enable RULE_ID         Enable a rule
          rule disable RULE_ID        Disable a rule
          rule show RULE_ID           Show rule details
          set OPTION VALUE            Set IDS configuration option
          clear                       Clear all events
          save [FILE]                 Save IDS database
          load [FILE]                 Load IDS database
          baseline                    Run security baseline check
        """
        args = shlex.split(arg)
        
        if not args:
            return IDSUtilities.do_ids.__doc__
        
        command = args[0]
        options = args[1:]
        
        # Process commands
        if command == "start":
            return IDSUtilities._ids_start(fs, cwd, options)
        elif command == "stop":
            return IDSUtilities._ids_stop(fs, cwd, options)
        elif command == "status":
            return IDSUtilities._ids_status(fs, cwd, options)
        elif command == "events":
            return IDSUtilities._ids_events(fs, cwd, options)
        elif command == "rules":
            return IDSUtilities._ids_rules(fs, cwd, options)
        elif command == "rule":
            if not options:
                return "ids rule: subcommand required"
            
            subcommand = options[0]
            suboptions = options[1:]
            
            if subcommand == "add":
                return IDSUtilities._ids_rule_add(fs, cwd, suboptions)
            elif subcommand == "remove":
                return IDSUtilities._ids_rule_remove(fs, cwd, suboptions)
            elif subcommand == "enable":
                return IDSUtilities._ids_rule_enable(fs, cwd, suboptions)
            elif subcommand == "disable":
                return IDSUtilities._ids_rule_disable(fs, cwd, suboptions)
            elif subcommand == "show":
                return IDSUtilities._ids_rule_show(fs, cwd, suboptions)
            else:
                return f"ids rule: unknown subcommand: {subcommand}"
        elif command == "set":
            return IDSUtilities._ids_set(fs, cwd, options)
        elif command == "clear":
            return IDSUtilities._ids_clear(fs, cwd, options)
        elif command == "save":
            return IDSUtilities._ids_save(fs, cwd, options)
        elif command == "load":
            return IDSUtilities._ids_load(fs, cwd, options)
        elif command == "baseline":
            return IDSUtilities._ids_baseline(fs, cwd, options)
        else:
            return f"ids: unknown command: {command}"
    
    @staticmethod
    def _ids_start(fs, cwd, options):
        """Start IDS monitoring"""
        success, message = IDSManager.start_monitoring()
        return message
    
    @staticmethod
    def _ids_stop(fs, cwd, options):
        """Stop IDS monitoring"""
        success, message = IDSManager.stop_monitoring()
        return message
    
    @staticmethod
    def _ids_status(fs, cwd, options):
        """Show IDS status"""
        # Get IDS status
        enabled = IDSManager._ids_config['enabled']
        alert_threshold = IDSManager._ids_config['alert_threshold']
        max_events = IDSManager._ids_config['max_events']
        check_interval = IDSManager._ids_config['check_interval']
        log_file = IDSManager._ids_config['log_file']
        baseline_interval = IDSManager._ids_config['baseline_interval']
        
        # Count events and rules
        events_count = len(IDSManager.list_events())
        rules_count = len(IDSManager.list_rules())
        
        # Format output
        output = ["IDS Status:"]
        output.append(f"  Monitoring: {'Enabled' if enabled else 'Disabled'}")
        output.append(f"  Alert threshold: {alert_threshold}")
        output.append(f"  Maximum events: {max_events}")
        output.append(f"  Check interval: {check_interval} seconds")
        output.append(f"  Baseline interval: {baseline_interval} seconds")
        output.append(f"  Log file: {log_file}")
        output.append(f"  Events: {events_count}")
        output.append(f"  Rules: {rules_count}")
        
        return "\n".join(output)
    
    @staticmethod
    def _ids_events(fs, cwd, options):
        """List IDS events"""
        # Parse options
        limit = 10  # Default limit
        event_type = None
        source = None
        min_severity = None
        
        i = 0
        while i < len(options):
            if options[i] == "--limit":
                if i + 1 < len(options):
                    try:
                        limit = int(options[i+1])
                        i += 2
                    except ValueError:
                        return f"ids events: invalid limit: {options[i+1]}"
                else:
                    return "ids events: option requires an argument -- '--limit'"
            elif options[i] == "--type":
                if i + 1 < len(options):
                    event_type = options[i+1]
                    i += 2
                else:
                    return "ids events: option requires an argument -- '--type'"
            elif options[i] == "--source":
                if i + 1 < len(options):
                    source = options[i+1]
                    i += 2
                else:
                    return "ids events: option requires an argument -- '--source'"
            elif options[i] == "--min-severity":
                if i + 1 < len(options):
                    try:
                        min_severity = int(options[i+1])
                        i += 2
                    except ValueError:
                        return f"ids events: invalid severity: {options[i+1]}"
                else:
                    return "ids events: option requires an argument -- '--min-severity'"
            elif options[i] == "--all":
                limit = None
                i += 1
            else:
                return f"ids events: unknown option: {options[i]}"
        
        # Get events
        events = IDSManager.list_events(
            limit=limit,
            event_type=event_type,
            source=source,
            min_severity=min_severity
        )
        
        if not events:
            return "No events found"
        
        # Format output
        output = [f"Events: {len(events)}"]
        output.append("TIME                 TYPE      SOURCE    SEV DETAILS")
        output.append("-" * 80)
        
        for event in events:
            # Format timestamp
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(event.timestamp))
            
            # Format details
            details_str = str(event.details)
            if len(details_str) > 40:
                details_str = details_str[:37] + "..."
            
            output.append(f"{timestamp} {event.event_type:<9} {event.source:<9} {event.severity:<3} {details_str}")
        
        return "\n".join(output)
    
    @staticmethod
    def _ids_rules(fs, cwd, options):
        """List IDS rules"""
        # Get rules
        rules = IDSManager.list_rules()
        
        if not rules:
            return "No rules found"
        
        # Format output
        output = [f"Rules: {len(rules)}"]
        output.append("ID       ENABLED TYPE      SEVERITY NAME")
        output.append("-" * 80)
        
        for rule in rules:
            # Format enabled
            enabled = "Yes" if rule.enabled else "No"
            
            output.append(f"{rule.rule_id:<9} {enabled:<7} {rule.event_type:<9} {rule.severity:<8} {rule.name}")
        
        return "\n".join(output)
    
    @staticmethod
    def _ids_rule_add(fs, cwd, options):
        """Add a rule"""
        # Parse options
        rule_id = None
        name = None
        description = None
        event_type = None
        pattern = None
        severity = 1
        enabled = True
        
        i = 0
        while i < len(options):
            if options[i] == "--id":
                if i + 1 < len(options):
                    rule_id = options[i+1]
                    i += 2
                else:
                    return "ids rule add: option requires an argument -- '--id'"
            elif options[i] == "--name":
                if i + 1 < len(options):
                    name = options[i+1]
                    i += 2
                else:
                    return "ids rule add: option requires an argument -- '--name'"
            elif options[i] == "--description":
                if i + 1 < len(options):
                    description = options[i+1]
                    i += 2
                else:
                    return "ids rule add: option requires an argument -- '--description'"
            elif options[i] == "--type":
                if i + 1 < len(options):
                    event_type = options[i+1]
                    i += 2
                else:
                    return "ids rule add: option requires an argument -- '--type'"
            elif options[i] == "--pattern":
                if i + 1 < len(options):
                    pattern = options[i+1]
                    i += 2
                else:
                    return "ids rule add: option requires an argument -- '--pattern'"
            elif options[i] == "--severity":
                if i + 1 < len(options):
                    try:
                        severity = int(options[i+1])
                        i += 2
                    except ValueError:
                        return f"ids rule add: invalid severity: {options[i+1]}"
                else:
                    return "ids rule add: option requires an argument -- '--severity'"
            elif options[i] == "--disabled":
                enabled = False
                i += 1
            else:
                return f"ids rule add: unknown option: {options[i]}"
        
        # Check required options
        if rule_id is None:
            return "ids rule add: rule ID is required (--id)"
        
        if name is None:
            return "ids rule add: rule name is required (--name)"
        
        if description is None:
            return "ids rule add: rule description is required (--description)"
        
        if event_type is None:
            return "ids rule add: event type is required (--type)"
        
        if pattern is None:
            return "ids rule add: pattern is required (--pattern)"
        
        # Add rule
        success, result = IDSManager.add_rule(
            rule_id=rule_id,
            name=name,
            description=description,
            event_type=event_type,
            pattern=pattern,
            severity=severity,
            enabled=enabled
        )
        
        if success:
            return f"Rule {rule_id} added"
        else:
            return f"Error: {result}"
    
    @staticmethod
    def _ids_rule_remove(fs, cwd, options):
        """Remove a rule"""
        if not options:
            return "ids rule remove: rule ID is required"
        
        rule_id = options[0]
        
        # Remove rule
        success, message = IDSManager.remove_rule(rule_id)
        
        return message
    
    @staticmethod
    def _ids_rule_enable(fs, cwd, options):
        """Enable a rule"""
        if not options:
            return "ids rule enable: rule ID is required"
        
        rule_id = options[0]
        
        # Enable rule
        success, message = IDSManager.enable_rule(rule_id)
        
        return message
    
    @staticmethod
    def _ids_rule_disable(fs, cwd, options):
        """Disable a rule"""
        if not options:
            return "ids rule disable: rule ID is required"
        
        rule_id = options[0]
        
        # Disable rule
        success, message = IDSManager.disable_rule(rule_id)
        
        return message
    
    @staticmethod
    def _ids_rule_show(fs, cwd, options):
        """Show rule details"""
        if not options:
            return "ids rule show: rule ID is required"
        
        rule_id = options[0]
        
        # Get rule
        rule = IDSManager.get_rule(rule_id)
        
        if rule is None:
            return f"Rule {rule_id} not found"
        
        # Format output
        output = [f"Rule: {rule.rule_id}"]
        output.append("-" * 50)
        output.append(f"Name: {rule.name}")
        output.append(f"Description: {rule.description}")
        output.append(f"Event Type: {rule.event_type}")
        output.append(f"Pattern: {rule.pattern}")
        output.append(f"Severity: {rule.severity}")
        output.append(f"Enabled: {'Yes' if rule.enabled else 'No'}")
        
        return "\n".join(output)
    
    @staticmethod
    def _ids_set(fs, cwd, options):
        """Set IDS configuration option"""
        if len(options) < 2:
            return "ids set: option and value required"
        
        option = options[0]
        value = options[1]
        
        if option == "interval":
            try:
                interval = int(value)
                success, message = IDSManager.set_check_interval(interval)
                return message
            except ValueError:
                return f"ids set: invalid interval: {value}"
        elif option == "threshold":
            try:
                threshold = int(value)
                success, message = IDSManager.set_alert_threshold(threshold)
                return message
            except ValueError:
                return f"ids set: invalid threshold: {value}"
        elif option == "max_events":
            try:
                max_events = int(value)
                success, message = IDSManager.set_max_events(max_events)
                return message
            except ValueError:
                return f"ids set: invalid max_events: {value}"
        elif option == "log_file":
            IDSManager._ids_config['log_file'] = value
            return f"Log file set to {value}"
        elif option == "baseline_interval":
            try:
                interval = int(value)
                IDSManager._ids_config['baseline_interval'] = interval
                return f"Baseline interval set to {interval} seconds"
            except ValueError:
                return f"ids set: invalid baseline_interval: {value}"
        else:
            return f"ids set: unknown option: {option}"
    
    @staticmethod
    def _ids_clear(fs, cwd, options):
        """Clear all events"""
        success, message = IDSManager.clear_events()
        return message
    
    @staticmethod
    def _ids_save(fs, cwd, options):
        """Save IDS database"""
        if options:
            db_file = options[0]
            
            # Resolve relative path
            if not os.path.isabs(db_file):
                db_file = os.path.join(cwd, db_file)
        else:
            db_file = os.path.join(os.path.expanduser('~'), '.kos', 'security', 'ids.json')
        
        success, message = IDSManager.save_database(db_file)
        return message
    
    @staticmethod
    def _ids_load(fs, cwd, options):
        """Load IDS database"""
        if options:
            db_file = options[0]
            
            # Resolve relative path
            if not os.path.isabs(db_file):
                db_file = os.path.join(cwd, db_file)
        else:
            db_file = os.path.join(os.path.expanduser('~'), '.kos', 'security', 'ids.json')
        
        success, message = IDSManager.load_database(db_file)
        return message
    
    @staticmethod
    def _ids_baseline(fs, cwd, options):
        """Run security baseline check"""
        # Run baseline checks
        IDSManager._run_baseline()
        
        return "Security baseline check completed"

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("ids", IDSUtilities.do_ids)

"""
File Integrity Monitoring Utilities for KOS Shell

This module provides commands for managing the KOS FIM system,
allowing users to monitor file integrity and detect unauthorized changes.
"""

import os
import sys
import logging
import shlex
import json
import time
from typing import Dict, List, Any, Optional, Tuple

# Import KOS components
from kos.security.fim import FIMManager, FileRecord, Alert

# Set up logging
logger = logging.getLogger('KOS.shell.commands.fim_utils')

class FIMUtilities:
    """File Integrity Monitoring commands for KOS shell"""
    
    @staticmethod
    def do_fim(fs, cwd, arg):
        """
        Manage KOS File Integrity Monitoring
        
        Usage: fim COMMAND [options]
        
        Commands:
          add FILE|DIR [options]      Add a file or directory to FIM database
          remove FILE|DIR             Remove a file or directory from FIM database
          check [FILE]                Check integrity of a file or all files
          list                        List monitored files
          status                      Show FIM status
          start                       Start automatic monitoring
          stop                        Stop automatic monitoring
          set OPTION VALUE            Set FIM configuration option
          ignore add PATTERN          Add ignore pattern
          ignore remove PATTERN       Remove ignore pattern
          ignore list                 List ignore patterns
          save [FILE]                 Save FIM database
          load [FILE]                 Load FIM database
        """
        args = shlex.split(arg)
        
        if not args:
            return FIMUtilities.do_fim.__doc__
        
        command = args[0]
        options = args[1:]
        
        # Process commands
        if command == "add":
            return FIMUtilities._fim_add(fs, cwd, options)
        elif command == "remove":
            return FIMUtilities._fim_remove(fs, cwd, options)
        elif command == "check":
            return FIMUtilities._fim_check(fs, cwd, options)
        elif command == "list":
            return FIMUtilities._fim_list(fs, cwd, options)
        elif command == "status":
            return FIMUtilities._fim_status(fs, cwd, options)
        elif command == "start":
            return FIMUtilities._fim_start(fs, cwd, options)
        elif command == "stop":
            return FIMUtilities._fim_stop(fs, cwd, options)
        elif command == "set":
            return FIMUtilities._fim_set(fs, cwd, options)
        elif command == "ignore":
            if not options:
                return "fim ignore: subcommand required"
            
            subcommand = options[0]
            suboptions = options[1:]
            
            if subcommand == "add":
                return FIMUtilities._fim_ignore_add(fs, cwd, suboptions)
            elif subcommand == "remove":
                return FIMUtilities._fim_ignore_remove(fs, cwd, suboptions)
            elif subcommand == "list":
                return FIMUtilities._fim_ignore_list(fs, cwd, suboptions)
            else:
                return f"fim ignore: unknown subcommand: {subcommand}"
        elif command == "save":
            return FIMUtilities._fim_save(fs, cwd, options)
        elif command == "load":
            return FIMUtilities._fim_load(fs, cwd, options)
        else:
            return f"fim: unknown command: {command}"
    
    @staticmethod
    def _fim_add(fs, cwd, options):
        """Add a file or directory to FIM database"""
        if not options:
            return "fim add: file or directory path required"
        
        # Parse options
        recursive = True
        path = options[0]
        
        for opt in options[1:]:
            if opt == "--no-recursive":
                recursive = False
            elif opt.startswith("--"):
                return f"fim add: unknown option: {opt}"
        
        # Resolve relative path
        if not os.path.isabs(path):
            path = os.path.join(cwd, path)
        
        # Check if path exists
        if not os.path.exists(path):
            return f"fim add: {path}: No such file or directory"
        
        # Add file or directory
        if os.path.isfile(path):
            success, message = FIMManager.add_file(path)
            return message
        elif os.path.isdir(path):
            success, result = FIMManager.add_directory(path, recursive)
            
            if success:
                return f"Added {len(result)} files to FIM database"
            else:
                return "\n".join(result)
        else:
            return f"fim add: {path}: Not a file or directory"
    
    @staticmethod
    def _fim_remove(fs, cwd, options):
        """Remove a file or directory from FIM database"""
        if not options:
            return "fim remove: file or directory path required"
        
        path = options[0]
        
        # Resolve relative path
        if not os.path.isabs(path):
            path = os.path.join(cwd, path)
        
        # Remove file or directory
        if os.path.isdir(path) or not os.path.exists(path):
            success, result = FIMManager.remove_directory(path)
            
            if success:
                return f"Removed {len(result)} files from FIM database"
            else:
                return "\n".join(result)
        else:
            success, message = FIMManager.remove_file(path)
            return message
    
    @staticmethod
    def _fim_check(fs, cwd, options):
        """Check integrity of a file or all files"""
        if options:
            path = options[0]
            
            # Resolve relative path
            if not os.path.isabs(path):
                path = os.path.join(cwd, path)
            
            # Check file
            integrity_intact, alerts = FIMManager.check_file(path)
            
            if integrity_intact:
                return f"File {path} integrity check: OK"
            elif alerts is None:
                return f"File {path} is not monitored"
            else:
                result = [f"File {path} integrity check: FAILED"]
                
                for alert in alerts:
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(alert['timestamp']))
                    result.append(f"  {timestamp} - {alert['alert_type']}: {alert['details']}")
                    
                    if alert['old_value'] is not None and alert['new_value'] is not None:
                        result.append(f"    Changed: {alert['old_value']} -> {alert['new_value']}")
                
                return "\n".join(result)
        else:
            # Check all files
            results = FIMManager.check_all_files()
            
            if not results:
                return "All monitored files integrity check: OK"
            else:
                output = ["File integrity check results:"]
                
                for file_path, alerts in results.items():
                    output.append(f"File {file_path}: FAILED")
                    
                    for alert in alerts:
                        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(alert['timestamp']))
                        output.append(f"  {timestamp} - {alert['alert_type']}: {alert['details']}")
                        
                        if alert['old_value'] is not None and alert['new_value'] is not None:
                            output.append(f"    Changed: {alert['old_value']} -> {alert['new_value']}")
                
                return "\n".join(output)
    
    @staticmethod
    def _fim_list(fs, cwd, options):
        """List monitored files"""
        files = FIMManager.list_monitored_files()
        
        if not files:
            return "No files are being monitored"
        
        # Format output
        output = [f"Total monitored files: {len(files)}"]
        
        for file_path in sorted(files):
            record = FIMManager.get_file_record(file_path)
            
            if record:
                last_checked = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(record.last_checked))
                output.append(f"{file_path} (Last checked: {last_checked})")
        
        return "\n".join(output)
    
    @staticmethod
    def _fim_status(fs, cwd, options):
        """Show FIM status"""
        # Get FIM status
        files_count = len(FIMManager.list_monitored_files())
        monitoring_enabled = FIMManager._fim_config['monitoring_enabled']
        check_interval = FIMManager._fim_config['check_interval']
        hash_algorithm = FIMManager._fim_config['hash_algorithm']
        alert_on_changes = FIMManager._fim_config['alert_on_changes']
        
        # Format output
        output = ["FIM Status:"]
        output.append(f"  Monitoring: {'Enabled' if monitoring_enabled else 'Disabled'}")
        output.append(f"  Monitored files: {files_count}")
        output.append(f"  Check interval: {check_interval} seconds")
        output.append(f"  Hash algorithm: {hash_algorithm}")
        output.append(f"  Alert on changes: {'Yes' if alert_on_changes else 'No'}")
        
        # Add ignore patterns
        ignore_patterns = FIMManager.list_ignore_patterns()
        if ignore_patterns:
            output.append("  Ignore patterns:")
            for pattern in ignore_patterns:
                output.append(f"    {pattern}")
        
        return "\n".join(output)
    
    @staticmethod
    def _fim_start(fs, cwd, options):
        """Start automatic monitoring"""
        success, message = FIMManager.start_monitoring()
        return message
    
    @staticmethod
    def _fim_stop(fs, cwd, options):
        """Stop automatic monitoring"""
        success, message = FIMManager.stop_monitoring()
        return message
    
    @staticmethod
    def _fim_set(fs, cwd, options):
        """Set FIM configuration option"""
        if len(options) < 2:
            return "fim set: option and value required"
        
        option = options[0]
        value = options[1]
        
        if option == "interval":
            try:
                interval = int(value)
                success, message = FIMManager.set_check_interval(interval)
                return message
            except ValueError:
                return f"fim set: invalid interval: {value}"
        elif option == "algorithm":
            success, message = FIMManager.set_hash_algorithm(value)
            return message
        elif option == "alert":
            if value.lower() in ["yes", "true", "1", "on"]:
                FIMManager._fim_config['alert_on_changes'] = True
                return "Alert on changes: enabled"
            elif value.lower() in ["no", "false", "0", "off"]:
                FIMManager._fim_config['alert_on_changes'] = False
                return "Alert on changes: disabled"
            else:
                return f"fim set: invalid value for alert: {value}"
        else:
            return f"fim set: unknown option: {option}"
    
    @staticmethod
    def _fim_ignore_add(fs, cwd, options):
        """Add ignore pattern"""
        if not options:
            return "fim ignore add: pattern required"
        
        pattern = options[0]
        
        success, message = FIMManager.add_ignore_pattern(pattern)
        return message
    
    @staticmethod
    def _fim_ignore_remove(fs, cwd, options):
        """Remove ignore pattern"""
        if not options:
            return "fim ignore remove: pattern required"
        
        pattern = options[0]
        
        success, message = FIMManager.remove_ignore_pattern(pattern)
        return message
    
    @staticmethod
    def _fim_ignore_list(fs, cwd, options):
        """List ignore patterns"""
        patterns = FIMManager.list_ignore_patterns()
        
        if not patterns:
            return "No ignore patterns defined"
        
        return "\n".join(patterns)
    
    @staticmethod
    def _fim_save(fs, cwd, options):
        """Save FIM database"""
        if options:
            db_file = options[0]
            
            # Resolve relative path
            if not os.path.isabs(db_file):
                db_file = os.path.join(cwd, db_file)
        else:
            db_file = os.path.join(os.path.expanduser('~'), '.kos', 'security', 'fim.json')
        
        success, message = FIMManager.save_database(db_file)
        return message
    
    @staticmethod
    def _fim_load(fs, cwd, options):
        """Load FIM database"""
        if options:
            db_file = options[0]
            
            # Resolve relative path
            if not os.path.isabs(db_file):
                db_file = os.path.join(cwd, db_file)
        else:
            db_file = os.path.join(os.path.expanduser('~'), '.kos', 'security', 'fim.json')
        
        success, message = FIMManager.load_database(db_file)
        return message

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("fim", FIMUtilities.do_fim)

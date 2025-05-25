"""
Security Policy Management Utilities for KOS Shell

This module provides commands for managing the KOS Security Policy system,
allowing users to define, enforce, and audit security policies across all
security components.
"""

import os
import sys
import logging
import shlex
import json
import time
from typing import Dict, List, Any, Optional, Tuple

# Import KOS components
from kos.security.policy import PolicyManager, SecurityPolicy
from kos.security.audit import AuditSystem

# Set up logging
logger = logging.getLogger('KOS.shell.commands.policy_utils')

class PolicyUtilities:
    """Security Policy Management commands for KOS shell"""
    
    @staticmethod
    def do_policy(fs, cwd, arg):
        """
        Manage KOS Security Policy System
        
        Usage: policy COMMAND [options]
        
        Commands:
          list                         List available policies
          show NAME                    Show policy details
          create NAME [options]        Create a new policy
          edit NAME [options]          Edit an existing policy
          delete NAME                  Delete a policy
          activate NAME                Activate a policy
          deactivate                   Deactivate current policy
          status                       Show policy status
          apply [NAME]                 Apply a policy (or active policy)
          export NAME FILE             Export a policy to a file
          import FILE [--overwrite]    Import a policy from a file
          validate NAME                Validate a policy
        """
        args = shlex.split(arg)
        
        if not args:
            return PolicyUtilities.do_policy.__doc__
        
        command = args[0]
        options = args[1:]
        
        # Process commands
        if command == "list":
            return PolicyUtilities._policy_list(fs, cwd, options)
        elif command == "show":
            return PolicyUtilities._policy_show(fs, cwd, options)
        elif command == "create":
            return PolicyUtilities._policy_create(fs, cwd, options)
        elif command == "edit":
            return PolicyUtilities._policy_edit(fs, cwd, options)
        elif command == "delete":
            return PolicyUtilities._policy_delete(fs, cwd, options)
        elif command == "activate":
            return PolicyUtilities._policy_activate(fs, cwd, options)
        elif command == "deactivate":
            return PolicyUtilities._policy_deactivate(fs, cwd, options)
        elif command == "status":
            return PolicyUtilities._policy_status(fs, cwd, options)
        elif command == "apply":
            return PolicyUtilities._policy_apply(fs, cwd, options)
        elif command == "export":
            return PolicyUtilities._policy_export(fs, cwd, options)
        elif command == "import":
            return PolicyUtilities._policy_import(fs, cwd, options)
        elif command == "validate":
            return PolicyUtilities._policy_validate(fs, cwd, options)
        else:
            return f"policy: unknown command: {command}"
    
    @staticmethod
    def _policy_list(fs, cwd, options):
        """List available policies"""
        policies = PolicyManager.list_policies()
        
        if not policies:
            return "No security policies available"
        
        # Get active policy
        active_policy = PolicyManager.get_active_policy()
        active_policy_name = active_policy.name if active_policy else None
        
        # Format output
        output = [f"Security Policies ({len(policies)}):"]
        output.append("NAME                    VERSION   AUTHOR                  DESCRIPTION")
        output.append("-" * 80)
        
        for name, policy in sorted(policies.items()):
            # Format active policy indicator
            active = "* " if name == active_policy_name else "  "
            
            # Format fields
            name_field = name[:22]
            version_field = policy.version[:8]
            author_field = policy.author[:22]
            description_field = policy.description[:30]
            
            # Add line
            output.append(f"{active}{name_field:<22} {version_field:<8} {author_field:<22} {description_field}")
        
        if active_policy_name:
            output.append("")
            output.append("* = active policy")
        
        return "\n".join(output)
    
    @staticmethod
    def _policy_show(fs, cwd, options):
        """Show policy details"""
        if not options:
            return "policy show: policy name required"
        
        policy_name = options[0]
        
        # Get policy
        policy = PolicyManager.get_policy(policy_name)
        if not policy:
            return f"policy show: policy not found: {policy_name}"
        
        # Format output
        output = [f"Security Policy: {policy.name}"]
        output.append("")
        output.append(f"Description: {policy.description}")
        output.append(f"Version: {policy.version}")
        output.append(f"Author: {policy.author}")
        output.append(f"Created: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(policy.created))}")
        output.append(f"Modified: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(policy.modified))}")
        output.append("")
        output.append("Settings:")
        
        for key, value in sorted(policy.settings.items()):
            output.append(f"  {key}: {value}")
        
        output.append("")
        output.append("Rules:")
        
        for component, rules in sorted(policy.rules.items()):
            output.append(f"  {component}:")
            
            if isinstance(rules, dict):
                for rule_key, rule_value in sorted(rules.items()):
                    if isinstance(rule_value, list):
                        output.append(f"    {rule_key}: ({len(rule_value)} items)")
                    else:
                        output.append(f"    {rule_key}: {rule_value}")
            else:
                output.append(f"    {rules}")
        
        if policy.metadata:
            output.append("")
            output.append("Metadata:")
            
            for key, value in sorted(policy.metadata.items()):
                if isinstance(value, dict):
                    output.append(f"  {key}:")
                    for subkey, subvalue in sorted(value.items()):
                        output.append(f"    {subkey}: {subvalue}")
                else:
                    output.append(f"  {key}: {value}")
        
        return "\n".join(output)
    
    @staticmethod
    def _policy_create(fs, cwd, options):
        """Create a new policy"""
        if not options:
            return "policy create: policy name required"
        
        policy_name = options[0]
        
        # Parse options
        description = ""
        author = ""
        template = None
        
        i = 1
        while i < len(options):
            if options[i] == "--description":
                if i + 1 < len(options):
                    description = options[i+1]
                    i += 2
                else:
                    return "policy create: option requires an argument -- '--description'"
            elif options[i] == "--author":
                if i + 1 < len(options):
                    author = options[i+1]
                    i += 2
                else:
                    return "policy create: option requires an argument -- '--author'"
            elif options[i] == "--template":
                if i + 1 < len(options):
                    template = options[i+1]
                    i += 2
                else:
                    return "policy create: option requires an argument -- '--template'"
            else:
                return f"policy create: unknown option: {options[i]}"
        
        # Check if template exists
        if template:
            template_policy = PolicyManager.get_policy(template)
            if not template_policy:
                return f"policy create: template policy not found: {template}"
            
            # Create policy from template
            settings = template_policy.settings.copy()
            rules = template_policy.rules.copy()
            metadata = template_policy.metadata.copy()
        else:
            # Create empty policy
            settings = {}
            rules = {}
            metadata = {}
        
        # Create policy
        success, result = PolicyManager.create_policy(
            name=policy_name,
            description=description,
            author=author,
            settings=settings,
            rules=rules,
            metadata=metadata
        )
        
        if not success:
            return f"policy create: {result}"
        
        # Add audit event
        AuditSystem.add_event(
            category='security_config',
            event_type='policy_created',
            user='console',
            source='policy_manager',
            details={'policy_name': policy_name},
            severity=3,
            outcome='success'
        )
        
        return f"Security policy created: {policy_name}"
    
    @staticmethod
    def _policy_edit(fs, cwd, options):
        """Edit an existing policy"""
        if not options:
            return "policy edit: policy name required"
        
        policy_name = options[0]
        
        # Get policy
        policy = PolicyManager.get_policy(policy_name)
        if not policy:
            return f"policy edit: policy not found: {policy_name}"
        
        # Parse options
        description = None
        author = None
        version = None
        
        i = 1
        while i < len(options):
            if options[i] == "--description":
                if i + 1 < len(options):
                    description = options[i+1]
                    i += 2
                else:
                    return "policy edit: option requires an argument -- '--description'"
            elif options[i] == "--author":
                if i + 1 < len(options):
                    author = options[i+1]
                    i += 2
                else:
                    return "policy edit: option requires an argument -- '--author'"
            elif options[i] == "--version":
                if i + 1 < len(options):
                    version = options[i+1]
                    i += 2
                else:
                    return "policy edit: option requires an argument -- '--version'"
            elif options[i] == "--settings":
                if i + 1 < len(options):
                    try:
                        settings_file = options[i+1]
                        
                        # Resolve relative path
                        if not os.path.isabs(settings_file):
                            settings_file = os.path.join(cwd, settings_file)
                        
                        # Read settings from file
                        with open(settings_file, 'r') as f:
                            settings = json.load(f)
                        
                        # Update policy settings
                        policy.settings = settings
                        
                        i += 2
                    except Exception as e:
                        return f"policy edit: error reading settings file: {e}"
                else:
                    return "policy edit: option requires an argument -- '--settings'"
            elif options[i] == "--rules":
                if i + 1 < len(options):
                    try:
                        rules_file = options[i+1]
                        
                        # Resolve relative path
                        if not os.path.isabs(rules_file):
                            rules_file = os.path.join(cwd, rules_file)
                        
                        # Read rules from file
                        with open(rules_file, 'r') as f:
                            rules = json.load(f)
                        
                        # Update policy rules
                        policy.rules = rules
                        
                        i += 2
                    except Exception as e:
                        return f"policy edit: error reading rules file: {e}"
                else:
                    return "policy edit: option requires an argument -- '--rules'"
            elif options[i] == "--metadata":
                if i + 1 < len(options):
                    try:
                        metadata_file = options[i+1]
                        
                        # Resolve relative path
                        if not os.path.isabs(metadata_file):
                            metadata_file = os.path.join(cwd, metadata_file)
                        
                        # Read metadata from file
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                        
                        # Update policy metadata
                        policy.metadata = metadata
                        
                        i += 2
                    except Exception as e:
                        return f"policy edit: error reading metadata file: {e}"
                else:
                    return "policy edit: option requires an argument -- '--metadata'"
            else:
                return f"policy edit: unknown option: {options[i]}"
        
        # Update policy
        success, result = PolicyManager.update_policy(
            name=policy_name,
            description=description,
            author=author,
            version=version
        )
        
        if not success:
            return f"policy edit: {result}"
        
        # Add audit event
        AuditSystem.add_event(
            category='security_config',
            event_type='policy_updated',
            user='console',
            source='policy_manager',
            details={'policy_name': policy_name},
            severity=3,
            outcome='success'
        )
        
        return f"Security policy updated: {policy_name}"
    
    @staticmethod
    def _policy_delete(fs, cwd, options):
        """Delete a policy"""
        if not options:
            return "policy delete: policy name required"
        
        policy_name = options[0]
        
        # Delete policy
        success, message = PolicyManager.delete_policy(policy_name)
        
        if success:
            # Add audit event
            AuditSystem.add_event(
                category='security_config',
                event_type='policy_deleted',
                user='console',
                source='policy_manager',
                details={'policy_name': policy_name},
                severity=3,
                outcome='success'
            )
        
        return message
    
    @staticmethod
    def _policy_activate(fs, cwd, options):
        """Activate a policy"""
        if not options:
            return "policy activate: policy name required"
        
        policy_name = options[0]
        
        # Parse options
        apply = True
        
        for i in range(1, len(options)):
            if options[i] == "--no-apply":
                apply = False
            else:
                return f"policy activate: unknown option: {options[i]}"
        
        # Activate policy
        success, message = PolicyManager.activate_policy(policy_name, apply=apply)
        
        if success:
            # Add audit event
            AuditSystem.add_event(
                category='security_config',
                event_type='policy_activated',
                user='console',
                source='policy_manager',
                details={'policy_name': policy_name, 'applied': apply},
                severity=3,
                outcome='success'
            )
        
        return message
    
    @staticmethod
    def _policy_deactivate(fs, cwd, options):
        """Deactivate current policy"""
        # Deactivate policy
        success, message = PolicyManager.deactivate_policy()
        
        if success:
            # Add audit event
            AuditSystem.add_event(
                category='security_config',
                event_type='policy_deactivated',
                user='console',
                source='policy_manager',
                details={},
                severity=3,
                outcome='success'
            )
        
        return message
    
    @staticmethod
    def _policy_status(fs, cwd, options):
        """Show policy status"""
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
        
        # Show key settings
        output.append("")
        output.append("Key Settings:")
        
        key_settings = [
            "enforce_mac", "enforce_acl", "enable_audit", "enable_fim",
            "enable_ids", "enable_network_monitor", "log_level",
            "password_min_length", "max_login_attempts"
        ]
        
        for key in key_settings:
            if key in active_policy.settings:
                output.append(f"  {key}: {active_policy.settings[key]}")
        
        # Show component summaries
        output.append("")
        output.append("Component Rules Summary:")
        
        for component, rules in sorted(active_policy.rules.items()):
            if isinstance(rules, dict):
                output.append(f"  {component}: {len(rules)} rule groups")
            elif isinstance(rules, list):
                output.append(f"  {component}: {len(rules)} rules")
            else:
                output.append(f"  {component}: configured")
        
        return "\n".join(output)
    
    @staticmethod
    def _policy_apply(fs, cwd, options):
        """Apply a policy"""
        # Determine which policy to apply
        if options:
            policy_name = options[0]
            policy = PolicyManager.get_policy(policy_name)
            
            if not policy:
                return f"policy apply: policy not found: {policy_name}"
        else:
            # Apply active policy
            policy = PolicyManager.get_active_policy()
            
            if not policy:
                return "policy apply: no active policy"
        
        # Apply policy
        success, message = PolicyManager.apply_policy(policy)
        
        if success:
            # Add audit event
            AuditSystem.add_event(
                category='security_config',
                event_type='policy_applied',
                user='console',
                source='policy_manager',
                details={'policy_name': policy.name},
                severity=3,
                outcome='success'
            )
        else:
            # Add audit event
            AuditSystem.add_event(
                category='security_config',
                event_type='policy_applied',
                user='console',
                source='policy_manager',
                details={'policy_name': policy.name, 'error': message},
                severity=3,
                outcome='failure'
            )
        
        return message
    
    @staticmethod
    def _policy_export(fs, cwd, options):
        """Export a policy to a file"""
        if len(options) < 2:
            return "policy export: policy name and file path required"
        
        policy_name = options[0]
        export_file = options[1]
        
        # Resolve relative path
        if not os.path.isabs(export_file):
            export_file = os.path.join(cwd, export_file)
        
        # Export policy
        success, message = PolicyManager.export_policy(policy_name, export_file)
        
        if success:
            # Add audit event
            AuditSystem.add_event(
                category='security_config',
                event_type='policy_exported',
                user='console',
                source='policy_manager',
                details={'policy_name': policy_name, 'file': export_file},
                severity=2,
                outcome='success'
            )
        
        return message
    
    @staticmethod
    def _policy_import(fs, cwd, options):
        """Import a policy from a file"""
        if not options:
            return "policy import: file path required"
        
        import_file = options[0]
        
        # Resolve relative path
        if not os.path.isabs(import_file):
            import_file = os.path.join(cwd, import_file)
        
        # Parse options
        overwrite = False
        
        for i in range(1, len(options)):
            if options[i] == "--overwrite":
                overwrite = True
            else:
                return f"policy import: unknown option: {options[i]}"
        
        # Import policy
        success, result = PolicyManager.import_policy(import_file, overwrite=overwrite)
        
        if success:
            policy = result
            
            # Add audit event
            AuditSystem.add_event(
                category='security_config',
                event_type='policy_imported',
                user='console',
                source='policy_manager',
                details={'policy_name': policy.name, 'file': import_file},
                severity=3,
                outcome='success'
            )
            
            return f"Security policy imported: {policy.name}"
        else:
            return f"policy import: {result}"
    
    @staticmethod
    def _policy_validate(fs, cwd, options):
        """Validate a policy"""
        if not options:
            return "policy validate: policy name required"
        
        policy_name = options[0]
        
        # Get policy
        policy = PolicyManager.get_policy(policy_name)
        if not policy:
            return f"policy validate: policy not found: {policy_name}"
        
        # Validate policy
        success, message = PolicyManager.validate_policy(policy)
        
        if success:
            return f"Security policy '{policy_name}' is valid"
        else:
            return f"Security policy '{policy_name}' is invalid: {message}"


def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("policy", PolicyUtilities.do_policy)

"""
PAM Utilities for KOS Shell

This module provides commands for managing the KOS PAM system,
allowing users to configure and manage authentication modules.
"""

import os
import sys
import logging
import shlex
from typing import Dict, List, Any, Optional, Tuple

# Import KOS components
from kos.security.pam import PAMManager, PAMItem, PAM_AUTH, PAM_ACCOUNT, PAM_SESSION, PAM_PASSWORD
from kos.security.pam import PAM_REQUIRED, PAM_REQUISITE, PAM_SUFFICIENT, PAM_OPTIONAL

# Set up logging
logger = logging.getLogger('KOS.shell.commands.pam_utils')

class PAMUtilities:
    """PAM commands for KOS shell"""
    
    @staticmethod
    def do_pam_list_services(fs, cwd, arg):
        """
        List configured PAM services
        
        Usage: pam_list_services
        """
        services = []
        
        for service in PAMManager._pam_configs.keys():
            config_items = PAMManager.get_service_config(service)
            services.append(f"{service} ({len(config_items)} entries)")
        
        if not services:
            return "No PAM services configured"
        
        return "\n".join(services)
    
    @staticmethod
    def do_pam_show_service(fs, cwd, arg):
        """
        Show PAM service configuration
        
        Usage: pam_show_service service_name
        """
        args = shlex.split(arg)
        
        if not args:
            return PAMUtilities.do_pam_show_service.__doc__
        
        service = args[0]
        config_items = PAMManager.get_service_config(service)
        
        if not config_items:
            return f"Service {service} not configured"
        
        output = [f"Service: {service}"]
        output.append("-" * 50)
        
        for item in config_items:
            output.append(f"{item.module_type}\t{item.control_flag}\t{item.module_path}\t{item.module_args}")
        
        return "\n".join(output)
    
    @staticmethod
    def do_pam_add_service(fs, cwd, arg):
        """
        Add a new PAM service
        
        Usage: pam_add_service service_name
        """
        args = shlex.split(arg)
        
        if not args:
            return PAMUtilities.do_pam_add_service.__doc__
        
        service = args[0]
        
        # Check if service already exists
        if service in PAMManager._pam_configs:
            return f"Service {service} already exists"
        
        # Create empty service
        PAMManager.add_service(service, [])
        
        return f"Service {service} created"
    
    @staticmethod
    def do_pam_remove_service(fs, cwd, arg):
        """
        Remove a PAM service
        
        Usage: pam_remove_service service_name
        """
        args = shlex.split(arg)
        
        if not args:
            return PAMUtilities.do_pam_remove_service.__doc__
        
        service = args[0]
        
        # Remove service
        success, message = PAMManager.remove_service(service)
        
        return message
    
    @staticmethod
    def do_pam_add_module(fs, cwd, arg):
        """
        Add a module to a PAM service
        
        Usage: pam_add_module service_name module_type control_flag module_path [module_args]
        
        Arguments:
          service_name          Name of the PAM service
          module_type           Module type (auth, account, session, password)
          control_flag          Control flag (required, requisite, sufficient, optional)
          module_path           Module path
          module_args           Module arguments (optional)
        """
        args = shlex.split(arg)
        
        if len(args) < 4:
            return PAMUtilities.do_pam_add_module.__doc__
        
        service = args[0]
        module_type = args[1]
        control_flag = args[2]
        module_path = args[3]
        module_args = " ".join(args[4:]) if len(args) > 4 else ""
        
        # Validate module type
        valid_types = {
            "auth": PAM_AUTH, 
            "account": PAM_ACCOUNT, 
            "session": PAM_SESSION, 
            "password": PAM_PASSWORD
        }
        
        if module_type not in valid_types:
            return f"Invalid module type: {module_type}. Must be one of: {', '.join(valid_types.keys())}"
        
        # Validate control flag
        valid_flags = {
            "required": PAM_REQUIRED, 
            "requisite": PAM_REQUISITE, 
            "sufficient": PAM_SUFFICIENT, 
            "optional": PAM_OPTIONAL
        }
        
        if control_flag not in valid_flags:
            return f"Invalid control flag: {control_flag}. Must be one of: {', '.join(valid_flags.keys())}"
        
        # Get current service config
        config_items = PAMManager.get_service_config(service)
        
        # Create new item
        new_item = PAMItem(
            module_type=valid_types[module_type],
            control_flag=valid_flags[control_flag],
            module_path=module_path,
            module_args=module_args
        )
        
        # Add item to config
        config_items.append(new_item)
        
        # Update service
        success, message = PAMManager.add_service(service, config_items)
        
        if success:
            return f"Module added to service {service}"
        else:
            return message
    
    @staticmethod
    def do_pam_remove_module(fs, cwd, arg):
        """
        Remove a module from a PAM service
        
        Usage: pam_remove_module service_name index
        
        Arguments:
          service_name          Name of the PAM service
          index                 Index of the module to remove (from 0)
        """
        args = shlex.split(arg)
        
        if len(args) < 2:
            return PAMUtilities.do_pam_remove_module.__doc__
        
        service = args[0]
        
        try:
            index = int(args[1])
        except ValueError:
            return "Index must be a number"
        
        # Get current service config
        config_items = PAMManager.get_service_config(service)
        
        if not config_items:
            return f"Service {service} not configured"
        
        if index < 0 or index >= len(config_items):
            return f"Invalid index: {index}. Must be between 0 and {len(config_items)-1}"
        
        # Remove item
        config_items.pop(index)
        
        # Update service
        success, message = PAMManager.add_service(service, config_items)
        
        if success:
            return f"Module removed from service {service}"
        else:
            return message
    
    @staticmethod
    def do_pam_test_auth(fs, cwd, arg):
        """
        Test PAM authentication
        
        Usage: pam_test_auth service_name username password
        """
        args = shlex.split(arg)
        
        if len(args) < 3:
            return PAMUtilities.do_pam_test_auth.__doc__
        
        service = args[0]
        username = args[1]
        password = args[2]
        
        # Test authentication
        success, message = PAMManager.authenticate(service, username, password)
        
        if success:
            return f"Authentication successful for user {username} using service {service}"
        else:
            return f"Authentication failed: {message}"
    
    @staticmethod
    def do_pam_save(fs, cwd, arg):
        """
        Save PAM configuration
        
        Usage: pam_save [config_file]
        """
        args = shlex.split(arg)
        
        # Determine config file
        if args:
            config_file = args[0]
            # Resolve relative path
            if not os.path.isabs(config_file):
                config_file = os.path.join(cwd, config_file)
        else:
            config_file = os.path.join(os.path.expanduser('~'), '.kos', 'security', 'pam.json')
        
        # Save config
        success, message = PAMManager.save_config(config_file)
        
        return message
    
    @staticmethod
    def do_pam_load(fs, cwd, arg):
        """
        Load PAM configuration
        
        Usage: pam_load [config_file]
        """
        args = shlex.split(arg)
        
        # Determine config file
        if args:
            config_file = args[0]
            # Resolve relative path
            if not os.path.isabs(config_file):
                config_file = os.path.join(cwd, config_file)
        else:
            config_file = os.path.join(os.path.expanduser('~'), '.kos', 'security', 'pam.json')
        
        # Load config
        success, message = PAMManager.load_config(config_file)
        
        return message
    
    @staticmethod
    def do_pam_reset(fs, cwd, arg):
        """
        Reset PAM configuration to defaults
        
        Usage: pam_reset
        """
        # Create default config
        success, message = PAMManager.create_default_config()
        
        return message

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("pam_list_services", PAMUtilities.do_pam_list_services)
    shell.register_command("pam_show_service", PAMUtilities.do_pam_show_service)
    shell.register_command("pam_add_service", PAMUtilities.do_pam_add_service)
    shell.register_command("pam_remove_service", PAMUtilities.do_pam_remove_service)
    shell.register_command("pam_add_module", PAMUtilities.do_pam_add_module)
    shell.register_command("pam_remove_module", PAMUtilities.do_pam_remove_module)
    shell.register_command("pam_test_auth", PAMUtilities.do_pam_test_auth)
    shell.register_command("pam_save", PAMUtilities.do_pam_save)
    shell.register_command("pam_load", PAMUtilities.do_pam_load)
    shell.register_command("pam_reset", PAMUtilities.do_pam_reset)

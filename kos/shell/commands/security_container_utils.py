"""
Security Container Utilities for KOS Shell

This module provides commands for managing KOS security containers,
focusing on enhanced isolation and security features.
"""

import os
import sys
import logging
import shlex
import json
from typing import Dict, List, Any, Optional, Union

# Import KOS components
from kos.security.containers import ContainerManager, Container, NetworkPolicy, ContainerResources, MountPoint
from kos.security.mac import SecurityContext, MACManager

# Set up logging
logger = logging.getLogger('KOS.shell.commands.security_container_utils')

class SecurityContainerUtilities:
    """Security Container commands for KOS shell"""
    
    @staticmethod
    def do_scontainer(fs, cwd, arg):
        """
        Manage KOS security containers
        
        Usage: scontainer COMMAND [options]
        
        Commands:
          create [options] NAME              Create a new security container
          delete CONTAINER                   Delete a security container
          start CONTAINER                    Start a security container
          stop CONTAINER                     Stop a security container
          pause CONTAINER                    Pause a security container
          resume CONTAINER                   Resume a paused security container
          exec CONTAINER COMMAND [ARG...]    Execute a command in a container
          list                               List security containers
          show CONTAINER                     Show container details
          mount CONTAINER HOST CONTAINER     Add a mount point to a container
          unmount CONTAINER PATH             Remove a mount point from a container
          resources CONTAINER [options]      Update container resource limits
          network CONTAINER [options]        Update container network policy
          save [FILE]                        Save container state
          load [FILE]                        Load container state
        """
        args = shlex.split(arg)
        
        if not args:
            return SecurityContainerUtilities.do_scontainer.__doc__
        
        command = args[0]
        options = args[1:]
        
        # Process commands
        if command == "create":
            return SecurityContainerUtilities._scontainer_create(options)
        elif command == "delete":
            return SecurityContainerUtilities._scontainer_delete(options)
        elif command == "start":
            return SecurityContainerUtilities._scontainer_start(options)
        elif command == "stop":
            return SecurityContainerUtilities._scontainer_stop(options)
        elif command == "pause":
            return SecurityContainerUtilities._scontainer_pause(options)
        elif command == "resume":
            return SecurityContainerUtilities._scontainer_resume(options)
        elif command == "exec":
            return SecurityContainerUtilities._scontainer_exec(options)
        elif command == "list":
            return SecurityContainerUtilities._scontainer_list(options)
        elif command == "show":
            return SecurityContainerUtilities._scontainer_show(options)
        elif command == "mount":
            return SecurityContainerUtilities._scontainer_mount(options)
        elif command == "unmount":
            return SecurityContainerUtilities._scontainer_unmount(options)
        elif command == "resources":
            return SecurityContainerUtilities._scontainer_resources(options)
        elif command == "network":
            return SecurityContainerUtilities._scontainer_network(options)
        elif command == "save":
            return SecurityContainerUtilities._scontainer_save(options)
        elif command == "load":
            return SecurityContainerUtilities._scontainer_load(options)
        else:
            return f"scontainer: '{command}' is not a valid command.\nSee 'scontainer --help'"
    
    @staticmethod
    def _scontainer_create(options):
        """Create a new security container"""
        # Parse options
        name = None
        security_user = "container"
        security_role = "container_r"
        security_type = "container_t"
        security_level = ""
        max_memory = ContainerResources.DEFAULT_MAX_MEMORY
        max_cpu = ContainerResources.DEFAULT_MAX_CPU
        max_processes = ContainerResources.DEFAULT_MAX_PROCESSES
        max_files = ContainerResources.DEFAULT_MAX_FILES
        max_disk = ContainerResources.DEFAULT_MAX_DISK
        
        i = 0
        while i < len(options):
            if options[i] == "--name":
                if i + 1 < len(options):
                    name = options[i+1]
                    i += 2
                else:
                    return "scontainer: option requires an argument -- '--name'"
            elif options[i] == "--security-user":
                if i + 1 < len(options):
                    security_user = options[i+1]
                    i += 2
                else:
                    return "scontainer: option requires an argument -- '--security-user'"
            elif options[i] == "--security-role":
                if i + 1 < len(options):
                    security_role = options[i+1]
                    i += 2
                else:
                    return "scontainer: option requires an argument -- '--security-role'"
            elif options[i] == "--security-type":
                if i + 1 < len(options):
                    security_type = options[i+1]
                    i += 2
                else:
                    return "scontainer: option requires an argument -- '--security-type'"
            elif options[i] == "--security-level":
                if i + 1 < len(options):
                    security_level = options[i+1]
                    i += 2
                else:
                    return "scontainer: option requires an argument -- '--security-level'"
            elif options[i] == "--max-memory":
                if i + 1 < len(options):
                    try:
                        max_memory = int(options[i+1])
                        i += 2
                    except ValueError:
                        return f"scontainer: invalid memory value: {options[i+1]}"
                else:
                    return "scontainer: option requires an argument -- '--max-memory'"
            elif options[i] == "--max-cpu":
                if i + 1 < len(options):
                    try:
                        max_cpu = float(options[i+1])
                        i += 2
                    except ValueError:
                        return f"scontainer: invalid CPU value: {options[i+1]}"
                else:
                    return "scontainer: option requires an argument -- '--max-cpu'"
            elif options[i] == "--max-processes":
                if i + 1 < len(options):
                    try:
                        max_processes = int(options[i+1])
                        i += 2
                    except ValueError:
                        return f"scontainer: invalid processes value: {options[i+1]}"
                else:
                    return "scontainer: option requires an argument -- '--max-processes'"
            elif options[i] == "--max-files":
                if i + 1 < len(options):
                    try:
                        max_files = int(options[i+1])
                        i += 2
                    except ValueError:
                        return f"scontainer: invalid files value: {options[i+1]}"
                else:
                    return "scontainer: option requires an argument -- '--max-files'"
            elif options[i] == "--max-disk":
                if i + 1 < len(options):
                    try:
                        max_disk = int(options[i+1])
                        i += 2
                    except ValueError:
                        return f"scontainer: invalid disk value: {options[i+1]}"
                else:
                    return "scontainer: option requires an argument -- '--max-disk'"
            else:
                if name is None:
                    name = options[i]
                    i += 1
                else:
                    return f"scontainer: unexpected argument: {options[i]}"
        
        if name is None:
            return "scontainer: container name is required"
        
        # Create security context
        security_context = SecurityContext(
            user=security_user,
            role=security_role,
            type=security_type,
            level=security_level
        )
        
        # Create resource limits
        resources = ContainerResources(
            max_memory=max_memory,
            max_cpu=max_cpu,
            max_processes=max_processes,
            max_files=max_files,
            max_disk=max_disk
        )
        
        # Create container
        success, result = ContainerManager.create_container(
            name=name,
            security_context=security_context,
            resources=resources
        )
        
        if success:
            container = result
            return f"Container '{name}' created with ID {container.id}"
        else:
            return f"Error: {result}"
    
    @staticmethod
    def _scontainer_delete(options):
        """Delete a security container"""
        if not options:
            return "scontainer: container ID or name is required"
        
        container_id = options[0]
        
        # Check if container exists by name
        container = ContainerManager.get_container_by_name(container_id)
        if container:
            container_id = container.id
        
        # Delete container
        success, message = ContainerManager.delete_container(container_id)
        
        return message
    
    @staticmethod
    def _scontainer_start(options):
        """Start a security container"""
        if not options:
            return "scontainer: container ID or name is required"
        
        container_id = options[0]
        
        # Check if container exists by name
        container = ContainerManager.get_container_by_name(container_id)
        if container:
            container_id = container.id
        
        # Start container
        success, message = ContainerManager.start_container(container_id)
        
        return message
    
    @staticmethod
    def _scontainer_stop(options):
        """Stop a security container"""
        if not options:
            return "scontainer: container ID or name is required"
        
        container_id = options[0]
        
        # Check if container exists by name
        container = ContainerManager.get_container_by_name(container_id)
        if container:
            container_id = container.id
        
        # Stop container
        success, message = ContainerManager.stop_container(container_id)
        
        return message
    
    @staticmethod
    def _scontainer_pause(options):
        """Pause a security container"""
        if not options:
            return "scontainer: container ID or name is required"
        
        container_id = options[0]
        
        # Check if container exists by name
        container = ContainerManager.get_container_by_name(container_id)
        if container:
            container_id = container.id
        
        # Pause container
        success, message = ContainerManager.pause_container(container_id)
        
        return message
    
    @staticmethod
    def _scontainer_resume(options):
        """Resume a paused security container"""
        if not options:
            return "scontainer: container ID or name is required"
        
        container_id = options[0]
        
        # Check if container exists by name
        container = ContainerManager.get_container_by_name(container_id)
        if container:
            container_id = container.id
        
        # Resume container
        success, message = ContainerManager.resume_container(container_id)
        
        return message
    
    @staticmethod
    def _scontainer_exec(options):
        """Execute a command in a security container"""
        if len(options) < 2:
            return "scontainer: container ID/name and command are required"
        
        container_id = options[0]
        command = " ".join(options[1:])
        
        # Check if container exists by name
        container = ContainerManager.get_container_by_name(container_id)
        if container:
            container_id = container.id
        
        # Execute command
        success, result = ContainerManager.execute_in_container(container_id, command)
        
        if success:
            output = []
            if result['stdout']:
                output.append(result['stdout'])
            if result['stderr']:
                output.append(result['stderr'])
            if not output:
                output.append(f"Command completed with exit code {result['exit_code']}")
            return "\n".join(output)
        else:
            return f"Error: {result}"
    
    @staticmethod
    def _scontainer_list(options):
        """List security containers"""
        containers = ContainerManager.list_containers()
        
        if not containers:
            return "No security containers found"
        
        # Format output
        output = ["ID                               NAME                STATUS              SECURITY CONTEXT"]
        
        for container in containers:
            # Format ID (truncated)
            id_short = container.id[:12]
            
            # Format security context
            security_context = f"{container.security_context.user}:{container.security_context.type}"
            
            output.append(f"{id_short:<32} {container.name:<20} {container.status:<20} {security_context}")
        
        return "\n".join(output)
    
    @staticmethod
    def _scontainer_show(options):
        """Show container details"""
        if not options:
            return "scontainer: container ID or name is required"
        
        container_id = options[0]
        
        # Get container
        container = ContainerManager.get_container(container_id)
        if not container:
            container = ContainerManager.get_container_by_name(container_id)
        
        if not container:
            return f"Error: Container '{container_id}' not found"
        
        # Format output
        output = [f"Container: {container.name} ({container.id})", "-" * 50]
        
        output.append(f"Status: {container.status}")
        output.append(f"Created: {container.created_at}")
        output.append(f"User ID: {container.user_id}")
        output.append("")
        
        output.append("Security Context:")
        output.append(f"  User: {container.security_context.user}")
        output.append(f"  Role: {container.security_context.role}")
        output.append(f"  Type: {container.security_context.type}")
        if container.security_context.level:
            output.append(f"  Level: {container.security_context.level}")
        output.append("")
        
        output.append("Resource Limits:")
        output.append(f"  Memory: {container.resources.max_memory} bytes (used: {container.resources.memory_usage})")
        output.append(f"  CPU: {container.resources.max_cpu} cores (used: {container.resources.cpu_usage})")
        output.append(f"  Processes: {container.resources.max_processes} (used: {container.resources.process_count})")
        output.append(f"  Files: {container.resources.max_files} (used: {container.resources.file_count})")
        output.append(f"  Disk: {container.resources.max_disk} bytes (used: {container.resources.disk_usage})")
        output.append("")
        
        output.append("Network Policy:")
        output.append(f"  Outbound: {'Allowed' if container.network_policy.allow_outbound else 'Blocked'}")
        output.append(f"  Inbound: {'Allowed' if container.network_policy.allow_inbound else 'Blocked'}")
        if container.network_policy.allowed_hosts:
            output.append(f"  Allowed Hosts: {', '.join(container.network_policy.allowed_hosts)}")
        if container.network_policy.allowed_ports:
            output.append(f"  Allowed Ports: {', '.join(map(str, container.network_policy.allowed_ports))}")
        output.append("")
        
        if container.mounts:
            output.append("Mount Points:")
            for mount in container.mounts:
                ro_flag = " (ro)" if mount.read_only else ""
                output.append(f"  {mount.host_path} -> {mount.container_path}{ro_flag}")
            output.append("")
        
        if container.processes:
            output.append("Running Processes:")
            for process in container.processes:
                output.append(f"  {process['id'][:8]} {process['command']}")
        
        return "\n".join(output)
    
    @staticmethod
    def _scontainer_mount(options):
        """Add a mount point to a container"""
        if len(options) < 3:
            return "scontainer: container ID/name, host path, and container path are required"
        
        container_id = options[0]
        host_path = options[1]
        container_path = options[2]
        read_only = False
        
        if len(options) > 3 and options[3] in ["ro", "readonly", "read-only"]:
            read_only = True
        
        # Check if container exists by name
        container = ContainerManager.get_container_by_name(container_id)
        if container:
            container_id = container.id
        
        # Add mount
        success, message = ContainerManager.add_mount(container_id, host_path, container_path, read_only)
        
        return message
    
    @staticmethod
    def _scontainer_unmount(options):
        """Remove a mount point from a container"""
        if len(options) < 2:
            return "scontainer: container ID/name and container path are required"
        
        container_id = options[0]
        container_path = options[1]
        
        # Check if container exists by name
        container = ContainerManager.get_container_by_name(container_id)
        if container:
            container_id = container.id
        
        # Remove mount
        success, message = ContainerManager.remove_mount(container_id, container_path)
        
        return message
    
    @staticmethod
    def _scontainer_resources(options):
        """Update container resource limits"""
        if not options:
            return "scontainer: container ID or name is required"
        
        container_id = options[0]
        options = options[1:]
        
        # Check if container exists by name
        container = ContainerManager.get_container_by_name(container_id)
        if container:
            container_id = container.id
        else:
            container = ContainerManager.get_container(container_id)
            if not container:
                return f"Error: Container '{container_id}' not found"
        
        # Get current resources
        current_resources = container.resources
        
        # Parse options
        max_memory = current_resources.max_memory
        max_cpu = current_resources.max_cpu
        max_processes = current_resources.max_processes
        max_files = current_resources.max_files
        max_disk = current_resources.max_disk
        
        i = 0
        while i < len(options):
            if options[i] == "--max-memory":
                if i + 1 < len(options):
                    try:
                        max_memory = int(options[i+1])
                        i += 2
                    except ValueError:
                        return f"scontainer: invalid memory value: {options[i+1]}"
                else:
                    return "scontainer: option requires an argument -- '--max-memory'"
            elif options[i] == "--max-cpu":
                if i + 1 < len(options):
                    try:
                        max_cpu = float(options[i+1])
                        i += 2
                    except ValueError:
                        return f"scontainer: invalid CPU value: {options[i+1]}"
                else:
                    return "scontainer: option requires an argument -- '--max-cpu'"
            elif options[i] == "--max-processes":
                if i + 1 < len(options):
                    try:
                        max_processes = int(options[i+1])
                        i += 2
                    except ValueError:
                        return f"scontainer: invalid processes value: {options[i+1]}"
                else:
                    return "scontainer: option requires an argument -- '--max-processes'"
            elif options[i] == "--max-files":
                if i + 1 < len(options):
                    try:
                        max_files = int(options[i+1])
                        i += 2
                    except ValueError:
                        return f"scontainer: invalid files value: {options[i+1]}"
                else:
                    return "scontainer: option requires an argument -- '--max-files'"
            elif options[i] == "--max-disk":
                if i + 1 < len(options):
                    try:
                        max_disk = int(options[i+1])
                        i += 2
                    except ValueError:
                        return f"scontainer: invalid disk value: {options[i+1]}"
                else:
                    return "scontainer: option requires an argument -- '--max-disk'"
            else:
                return f"scontainer: unexpected argument: {options[i]}"
        
        # Create new resources
        resources = ContainerResources(
            max_memory=max_memory,
            max_cpu=max_cpu,
            max_processes=max_processes,
            max_files=max_files,
            max_disk=max_disk
        )
        
        # Update resources
        success, message = ContainerManager.update_resources(container_id, resources)
        
        return message
    
    @staticmethod
    def _scontainer_network(options):
        """Update container network policy"""
        if not options:
            return "scontainer: container ID or name is required"
        
        container_id = options[0]
        options = options[1:]
        
        # Check if container exists by name
        container = ContainerManager.get_container_by_name(container_id)
        if container:
            container_id = container.id
        else:
            container = ContainerManager.get_container(container_id)
            if not container:
                return f"Error: Container '{container_id}' not found"
        
        # Get current network policy
        current_policy = container.network_policy
        
        # Parse options
        allow_outbound = current_policy.allow_outbound
        allow_inbound = current_policy.allow_inbound
        allowed_hosts = current_policy.allowed_hosts.copy()
        allowed_ports = current_policy.allowed_ports.copy()
        
        i = 0
        while i < len(options):
            if options[i] == "--allow-outbound":
                allow_outbound = True
                i += 1
            elif options[i] == "--block-outbound":
                allow_outbound = False
                i += 1
            elif options[i] == "--allow-inbound":
                allow_inbound = True
                i += 1
            elif options[i] == "--block-inbound":
                allow_inbound = False
                i += 1
            elif options[i] == "--add-host":
                if i + 1 < len(options):
                    host = options[i+1]
                    if host not in allowed_hosts:
                        allowed_hosts.append(host)
                    i += 2
                else:
                    return "scontainer: option requires an argument -- '--add-host'"
            elif options[i] == "--remove-host":
                if i + 1 < len(options):
                    host = options[i+1]
                    if host in allowed_hosts:
                        allowed_hosts.remove(host)
                    i += 2
                else:
                    return "scontainer: option requires an argument -- '--remove-host'"
            elif options[i] == "--add-port":
                if i + 1 < len(options):
                    try:
                        port = int(options[i+1])
                        if port not in allowed_ports:
                            allowed_ports.append(port)
                        i += 2
                    except ValueError:
                        return f"scontainer: invalid port value: {options[i+1]}"
                else:
                    return "scontainer: option requires an argument -- '--add-port'"
            elif options[i] == "--remove-port":
                if i + 1 < len(options):
                    try:
                        port = int(options[i+1])
                        if port in allowed_ports:
                            allowed_ports.remove(port)
                        i += 2
                    except ValueError:
                        return f"scontainer: invalid port value: {options[i+1]}"
                else:
                    return "scontainer: option requires an argument -- '--remove-port'"
            elif options[i] == "--reset-hosts":
                allowed_hosts = []
                i += 1
            elif options[i] == "--reset-ports":
                allowed_ports = []
                i += 1
            else:
                return f"scontainer: unexpected argument: {options[i]}"
        
        # Create new network policy
        network_policy = NetworkPolicy(
            allow_outbound=allow_outbound,
            allow_inbound=allow_inbound,
            allowed_hosts=allowed_hosts,
            allowed_ports=allowed_ports
        )
        
        # Update network policy
        success, message = ContainerManager.update_network_policy(container_id, network_policy)
        
        return message
    
    @staticmethod
    def _scontainer_save(options):
        """Save container state"""
        # Determine state file
        if options:
            state_file = options[0]
        else:
            state_file = os.path.join(os.path.expanduser('~'), '.kos', 'security', 'containers.json')
        
        # Save state
        success, message = ContainerManager.save_state(state_file)
        
        return message
    
    @staticmethod
    def _scontainer_load(options):
        """Load container state"""
        # Determine state file
        if options:
            state_file = options[0]
        else:
            state_file = os.path.join(os.path.expanduser('~'), '.kos', 'security', 'containers.json')
        
        # Load state
        success, message = ContainerManager.load_state(state_file)
        
        return message

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("scontainer", SecurityContainerUtilities.do_scontainer)

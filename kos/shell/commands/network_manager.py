"""
Network Management Utilities for KOS Shell

This module provides network management commands for KOS.
"""

import os
import sys
import time
import logging
import json
import datetime
import ipaddress
import shlex
from typing import Dict, List, Any, Optional, Union

# Import KOS components
from kos.layer import klayer
from kos.network import NetworkManager, RouteManager, Network, Route
from kos.container import ContainerManager

# Set up logging
logger = logging.getLogger('KOS.shell.commands.network_manager')

class NetworkUtilities:
    """Network management commands for KOS shell"""
    
    @staticmethod
    def do_network(fs, cwd, arg):
        """
        Manage KOS networks
        
        Usage: network COMMAND [options]
        
        Commands:
          create [options]                Create a network
          ls [options]                    List networks
          inspect NETWORK                 Display detailed information on a network
          rm NETWORK                      Remove a network
          connect NETWORK CONTAINER       Connect a container to a network
          disconnect NETWORK CONTAINER    Disconnect a container from a network
          route [COMMAND]                 Manage routes
        """
        args = shlex.split(arg)
        
        if not args:
            return NetworkUtilities.do_network.__doc__
        
        command = args[0]
        options = args[1:]
        
        # Process commands
        if command == "create":
            return NetworkUtilities._network_create(options)
        elif command == "ls":
            return NetworkUtilities._network_ls(options)
        elif command == "inspect":
            return NetworkUtilities._network_inspect(options)
        elif command == "rm":
            return NetworkUtilities._network_rm(options)
        elif command == "connect":
            return NetworkUtilities._network_connect(options)
        elif command == "disconnect":
            return NetworkUtilities._network_disconnect(options)
        elif command == "route":
            return NetworkUtilities._network_route(options)
        else:
            return f"network: '{command}' is not a network command.\nSee 'network --help'"
    
    @staticmethod
    def _network_create(options):
        """Create a network"""
        # Parse options
        name = None
        subnet = None
        gateway = None
        driver = "bridge"
        internal = False
        
        i = 0
        while i < len(options):
            if options[i] == "--name":
                if i + 1 < len(options):
                    name = options[i+1]
                    i += 2
                else:
                    return "network create: option requires an argument -- '--name'"
            elif options[i] == "--subnet":
                if i + 1 < len(options):
                    subnet = options[i+1]
                    i += 2
                else:
                    return "network create: option requires an argument -- '--subnet'"
            elif options[i] == "--gateway":
                if i + 1 < len(options):
                    gateway = options[i+1]
                    i += 2
                else:
                    return "network create: option requires an argument -- '--gateway'"
            elif options[i] == "--driver":
                if i + 1 < len(options):
                    driver = options[i+1]
                    i += 2
                else:
                    return "network create: option requires an argument -- '--driver'"
            elif options[i] == "--internal":
                internal = True
                i += 1
            else:
                i += 1
        
        # Validate required options
        if not name:
            return "network create: '--name' is required"
        
        if not subnet:
            return "network create: '--subnet' is required"
        
        # Create network
        success, message, network = NetworkManager.create_network(
            name=name,
            subnet=subnet,
            gateway=gateway,
            driver=driver,
            internal=internal
        )
        
        if not success:
            return f"network create: {message}"
        
        return network.id
    
    @staticmethod
    def _network_ls(options):
        """List networks"""
        # Get networks
        networks = NetworkManager.list_networks()
        
        # Format output
        result = ["NETWORK ID          NAME                DRIVER              SUBNET"]
        
        for network in networks:
            result.append(f"{network.id:<20} {network.name:<20} {network.driver:<20} {network.subnet}")
        
        return "\n".join(result)
    
    @staticmethod
    def _network_inspect(options):
        """Inspect a network"""
        if not options:
            return "network inspect: network name or ID is required"
        
        network_id = options[0]
        
        # Get network
        network = NetworkManager.get_network(network_id)
        if not network:
            network = NetworkManager.get_network_by_name(network_id)
        
        if not network:
            return f"network inspect: network '{network_id}' not found"
        
        # Format output
        return json.dumps(network.to_dict(), indent=2)
    
    @staticmethod
    def _network_rm(options):
        """Remove a network"""
        if not options:
            return "network rm: network name or ID is required"
        
        network_id = options[0]
        
        # Get network
        network = NetworkManager.get_network(network_id)
        if not network:
            network = NetworkManager.get_network_by_name(network_id)
        
        if not network:
            return f"network rm: network '{network_id}' not found"
        
        # Remove network
        success, message = NetworkManager.remove_network(network.id)
        
        if not success:
            return f"network rm: {message}"
        
        return network.id
    
    @staticmethod
    def _network_connect(options):
        """Connect a container to a network"""
        if len(options) < 2:
            return "network connect: network and container ID/name are required"
        
        network_id = options[0]
        container_id = options[1]
        
        # Parse additional options
        ipv4_address = None
        
        i = 2
        while i < len(options):
            if options[i] == "--ip":
                if i + 1 < len(options):
                    ipv4_address = options[i+1]
                    i += 2
                else:
                    return "network connect: option requires an argument -- '--ip'"
            else:
                i += 1
        
        # Connect container to network
        success, message = NetworkManager.connect_container(
            network_id=network_id,
            container_id=container_id,
            ipv4_address=ipv4_address
        )
        
        if not success:
            return f"network connect: {message}"
        
        return message
    
    @staticmethod
    def _network_disconnect(options):
        """Disconnect a container from a network"""
        if len(options) < 2:
            return "network disconnect: network and container ID/name are required"
        
        network_id = options[0]
        container_id = options[1]
        
        # Disconnect container from network
        success, message = NetworkManager.disconnect_container(
            network_id=network_id,
            container_id=container_id
        )
        
        if not success:
            return f"network disconnect: {message}"
        
        return message
    
    @staticmethod
    def _network_route(options):
        """Manage routes"""
        if not options:
            # Show routes
            routes = RouteManager.list_routes()
            
            # Format output
            result = ["Destination         Gateway            Flags  Interface  Metric"]
            
            for route in routes:
                result.append(f"{route.destination:<20} {route.gateway:<20} {route.flags:<6} {route.interface:<10} {route.metric}")
            
            return "\n".join(result)
        
        command = options[0]
        suboptions = options[1:]
        
        if command == "add":
            # Parse options
            if len(suboptions) < 3:
                return "network route add: destination, gateway, and interface are required"
            
            destination = suboptions[0]
            gateway = suboptions[1]
            interface = suboptions[2]
            
            # Parse metric if specified
            metric = 0
            if len(suboptions) > 3:
                try:
                    metric = int(suboptions[3])
                except ValueError:
                    return f"network route add: invalid metric: {suboptions[3]}"
            
            # Add route
            success, message = RouteManager.add_route(
                destination=destination,
                gateway=gateway,
                interface=interface,
                metric=metric
            )
            
            if not success:
                return f"network route add: {message}"
            
            return message
        
        elif command == "del" or command == "delete":
            # Parse options
            if not suboptions:
                return "network route del: destination is required"
            
            destination = suboptions[0]
            
            # Remove route
            success, message = RouteManager.remove_route(destination=destination)
            
            if not success:
                return f"network route del: {message}"
            
            return message
        
        else:
            return f"network route: '{command}' is not a valid command"

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("network", NetworkUtilities.do_network)

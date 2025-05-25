"""
Network Security Monitor Utilities for KOS Shell

This module provides commands for managing the KOS Network Security Monitor,
allowing users to detect and respond to suspicious network activity.
"""

import os
import sys
import logging
import shlex
import json
import time
import ipaddress
from typing import Dict, List, Any, Optional, Tuple

# Import KOS components
from kos.security.network_monitor import NetworkMonitor, NetworkConnection, HostInfo

# Set up logging
logger = logging.getLogger('KOS.shell.commands.network_monitor_utils')

class NetworkMonitorUtilities:
    """Network Security Monitor commands for KOS shell"""
    
    @staticmethod
    def do_netmon(fs, cwd, arg):
        """
        Manage KOS Network Security Monitor
        
        Usage: netmon COMMAND [options]
        
        Commands:
          start                       Start network monitoring
          stop                        Stop network monitoring
          status                      Show monitoring status
          connections [options]       List current connections
          history [options]           List connection history
          hosts [options]             List known hosts
          blacklist list              List blacklisted addresses
          blacklist add ADDR          Add address to blacklist
          blacklist remove ADDR       Remove address from blacklist
          blacklist check ADDR        Check if address is blacklisted
          whitelist list              List whitelisted addresses
          whitelist add ADDR          Add address to whitelist
          whitelist remove ADDR       Remove address from whitelist
          whitelist check ADDR        Check if address is whitelisted
          host tag add ADDR TAG       Add tag to host
          host tag remove ADDR TAG    Remove tag from host
          set OPTION VALUE            Set configuration option
          save [FILE]                 Save network monitor database
          load [FILE]                 Load network monitor database
        """
        args = shlex.split(arg)
        
        if not args:
            return NetworkMonitorUtilities.do_netmon.__doc__
        
        command = args[0]
        options = args[1:]
        
        # Process commands
        if command == "start":
            return NetworkMonitorUtilities._netmon_start(fs, cwd, options)
        elif command == "stop":
            return NetworkMonitorUtilities._netmon_stop(fs, cwd, options)
        elif command == "status":
            return NetworkMonitorUtilities._netmon_status(fs, cwd, options)
        elif command == "connections":
            return NetworkMonitorUtilities._netmon_connections(fs, cwd, options)
        elif command == "history":
            return NetworkMonitorUtilities._netmon_history(fs, cwd, options)
        elif command == "hosts":
            return NetworkMonitorUtilities._netmon_hosts(fs, cwd, options)
        elif command == "blacklist":
            if not options:
                return "netmon blacklist: subcommand required"
            
            subcommand = options[0]
            suboptions = options[1:]
            
            if subcommand == "list":
                return NetworkMonitorUtilities._netmon_blacklist_list(fs, cwd, suboptions)
            elif subcommand == "add":
                return NetworkMonitorUtilities._netmon_blacklist_add(fs, cwd, suboptions)
            elif subcommand == "remove":
                return NetworkMonitorUtilities._netmon_blacklist_remove(fs, cwd, suboptions)
            elif subcommand == "check":
                return NetworkMonitorUtilities._netmon_blacklist_check(fs, cwd, suboptions)
            else:
                return f"netmon blacklist: unknown subcommand: {subcommand}"
        elif command == "whitelist":
            if not options:
                return "netmon whitelist: subcommand required"
            
            subcommand = options[0]
            suboptions = options[1:]
            
            if subcommand == "list":
                return NetworkMonitorUtilities._netmon_whitelist_list(fs, cwd, suboptions)
            elif subcommand == "add":
                return NetworkMonitorUtilities._netmon_whitelist_add(fs, cwd, suboptions)
            elif subcommand == "remove":
                return NetworkMonitorUtilities._netmon_whitelist_remove(fs, cwd, suboptions)
            elif subcommand == "check":
                return NetworkMonitorUtilities._netmon_whitelist_check(fs, cwd, suboptions)
            else:
                return f"netmon whitelist: unknown subcommand: {subcommand}"
        elif command == "host":
            if not options or options[0] != "tag" or len(options) < 2:
                return "netmon host: invalid subcommand (use 'tag add' or 'tag remove')"
            
            if options[1] == "add" and len(options) >= 4:
                addr = options[2]
                tag = options[3]
                return NetworkMonitorUtilities._netmon_host_tag_add(fs, cwd, [addr, tag])
            elif options[1] == "remove" and len(options) >= 4:
                addr = options[2]
                tag = options[3]
                return NetworkMonitorUtilities._netmon_host_tag_remove(fs, cwd, [addr, tag])
            else:
                return "netmon host tag: usage: netmon host tag add|remove ADDR TAG"
        elif command == "set":
            return NetworkMonitorUtilities._netmon_set(fs, cwd, options)
        elif command == "save":
            return NetworkMonitorUtilities._netmon_save(fs, cwd, options)
        elif command == "load":
            return NetworkMonitorUtilities._netmon_load(fs, cwd, options)
        else:
            return f"netmon: unknown command: {command}"
    
    @staticmethod
    def _netmon_start(fs, cwd, options):
        """Start network monitoring"""
        success, message = NetworkMonitor.start_monitoring()
        return message
    
    @staticmethod
    def _netmon_stop(fs, cwd, options):
        """Stop network monitoring"""
        success, message = NetworkMonitor.stop_monitoring()
        return message
    
    @staticmethod
    def _netmon_status(fs, cwd, options):
        """Show network monitoring status"""
        # Get status
        enabled = NetworkMonitor._netmon_config['enabled']
        check_interval = NetworkMonitor._netmon_config['check_interval']
        max_connections = NetworkMonitor._netmon_config['max_connections']
        max_rate = NetworkMonitor._netmon_config['max_rate']
        alert_on_blacklist = NetworkMonitor._netmon_config['alert_on_blacklist']
        alert_on_new_hosts = NetworkMonitor._netmon_config['alert_on_new_hosts']
        log_file = NetworkMonitor._netmon_config['log_file']
        
        # Count current connections, history, and hosts
        current_connections = len(NetworkMonitor._connections)
        connection_history = len(NetworkMonitor._connection_history)
        known_hosts = len(NetworkMonitor._known_hosts)
        blacklist = len(NetworkMonitor._blacklist)
        whitelist = len(NetworkMonitor._whitelist)
        
        # Format output
        output = ["Network Security Monitor Status:"]
        output.append(f"  Monitoring: {'Enabled' if enabled else 'Disabled'}")
        output.append(f"  Check Interval: {check_interval} seconds")
        output.append(f"  Maximum Connection History: {max_connections}")
        output.append(f"  Maximum Connection Rate: {max_rate} per minute")
        output.append(f"  Alert on Blacklisted Connections: {'Yes' if alert_on_blacklist else 'No'}")
        output.append(f"  Alert on New Hosts: {'Yes' if alert_on_new_hosts else 'No'}")
        output.append(f"  Log File: {log_file}")
        output.append(f"  Current Connections: {current_connections}")
        output.append(f"  Connection History: {connection_history}")
        output.append(f"  Known Hosts: {known_hosts}")
        output.append(f"  Blacklisted Addresses: {blacklist}")
        output.append(f"  Whitelisted Addresses: {whitelist}")
        
        return "\n".join(output)
    
    @staticmethod
    def _netmon_connections(fs, cwd, options):
        """List current connections"""
        # Update connections
        NetworkMonitor.update_connections()
        
        # Get current connections
        connections = []
        for key, conn in NetworkMonitor._connections.items():
            connections.append(conn)
        
        if not connections:
            return "No active connections found"
        
        # Format output
        output = [f"Current Connections: {len(connections)}"]
        output.append("PROTOCOL LOCAL                 REMOTE                STATE    PROGRAM")
        output.append("-" * 80)
        
        for conn in connections:
            local = f"{conn.local_addr}:{conn.local_port}"
            remote = f"{conn.remote_addr}:{conn.remote_port}"
            program = conn.program or "unknown"
            
            output.append(f"{conn.protocol:<8} {local:<22} {remote:<22} {conn.state:<8} {program}")
        
        return "\n".join(output)
    
    @staticmethod
    def _netmon_history(fs, cwd, options):
        """List connection history"""
        # Parse options
        limit = 10  # Default limit
        protocol = None
        remote_addr = None
        remote_port = None
        local_addr = None
        local_port = None
        program = None
        time_range = None
        
        i = 0
        while i < len(options):
            if options[i] == "--limit":
                if i + 1 < len(options):
                    try:
                        limit = int(options[i+1])
                        i += 2
                    except ValueError:
                        return f"netmon history: invalid limit: {options[i+1]}"
                else:
                    return "netmon history: option requires an argument -- '--limit'"
            elif options[i] == "--protocol":
                if i + 1 < len(options):
                    protocol = options[i+1]
                    i += 2
                else:
                    return "netmon history: option requires an argument -- '--protocol'"
            elif options[i] == "--remote-addr":
                if i + 1 < len(options):
                    remote_addr = options[i+1]
                    i += 2
                else:
                    return "netmon history: option requires an argument -- '--remote-addr'"
            elif options[i] == "--remote-port":
                if i + 1 < len(options):
                    try:
                        remote_port = int(options[i+1])
                        i += 2
                    except ValueError:
                        return f"netmon history: invalid port: {options[i+1]}"
                else:
                    return "netmon history: option requires an argument -- '--remote-port'"
            elif options[i] == "--local-addr":
                if i + 1 < len(options):
                    local_addr = options[i+1]
                    i += 2
                else:
                    return "netmon history: option requires an argument -- '--local-addr'"
            elif options[i] == "--local-port":
                if i + 1 < len(options):
                    try:
                        local_port = int(options[i+1])
                        i += 2
                    except ValueError:
                        return f"netmon history: invalid port: {options[i+1]}"
                else:
                    return "netmon history: option requires an argument -- '--local-port'"
            elif options[i] == "--program":
                if i + 1 < len(options):
                    program = options[i+1]
                    i += 2
                else:
                    return "netmon history: option requires an argument -- '--program'"
            elif options[i] == "--time-range":
                if i + 1 < len(options):
                    try:
                        time_range = int(options[i+1])
                        i += 2
                    except ValueError:
                        return f"netmon history: invalid time range: {options[i+1]}"
                else:
                    return "netmon history: option requires an argument -- '--time-range'"
            elif options[i] == "--all":
                limit = None
                i += 1
            else:
                return f"netmon history: unknown option: {options[i]}"
        
        # Get connection history
        connections = NetworkMonitor.get_connection_history(
            protocol=protocol,
            local_addr=local_addr,
            local_port=local_port,
            remote_addr=remote_addr,
            remote_port=remote_port,
            program=program,
            time_range=time_range
        )
        
        if not connections:
            return "No connection history found"
        
        # Apply limit
        if limit is not None and len(connections) > limit:
            connections = connections[:limit]
        
        # Format output
        output = [f"Connection History: {len(connections)}"]
        output.append("TIME                 PROTOCOL LOCAL                 REMOTE                STATE    PROGRAM")
        output.append("-" * 100)
        
        for conn in connections:
            # Format timestamp
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(conn.timestamp))
            local = f"{conn.local_addr}:{conn.local_port}"
            remote = f"{conn.remote_addr}:{conn.remote_port}"
            program = conn.program or "unknown"
            
            output.append(f"{timestamp} {conn.protocol:<8} {local:<22} {remote:<22} {conn.state:<8} {program}")
        
        return "\n".join(output)
    
    @staticmethod
    def _netmon_hosts(fs, cwd, options):
        """List known hosts"""
        # Parse options
        with_tags = False
        tag_filter = None
        
        i = 0
        while i < len(options):
            if options[i] == "--with-tags":
                with_tags = True
                i += 1
            elif options[i] == "--tag":
                if i + 1 < len(options):
                    tag_filter = options[i+1]
                    i += 2
                else:
                    return "netmon hosts: option requires an argument -- '--tag'"
            else:
                return f"netmon hosts: unknown option: {options[i]}"
        
        # Get known hosts
        hosts = NetworkMonitor.get_known_hosts()
        
        if not hosts:
            return "No known hosts found"
        
        # Apply tag filter
        if tag_filter is not None:
            hosts = {addr: host for addr, host in hosts.items() if tag_filter in host.tags}
            
            if not hosts:
                return f"No hosts found with tag: {tag_filter}"
        
        # Format output
        output = [f"Known Hosts: {len(hosts)}"]
        if with_tags:
            output.append("ADDRESS            HOSTNAME                       PORTS    CONNECTIONS  TAGS")
        else:
            output.append("ADDRESS            HOSTNAME                       PORTS    CONNECTIONS")
        output.append("-" * 100)
        
        for addr, host in sorted(hosts.items()):
            hostname = host.hostname or ""
            if len(hostname) > 30:
                hostname = hostname[:27] + "..."
            
            ports = ", ".join(str(p) for p in sorted(host.ports)[:5])
            if len(host.ports) > 5:
                ports += ", ..."
            
            if with_tags:
                tags = ", ".join(host.tags)
                output.append(f"{addr:<18} {hostname:<30} {ports:<8} {host.connection_count:<11} {tags}")
            else:
                output.append(f"{addr:<18} {hostname:<30} {ports:<8} {host.connection_count}")
        
        return "\n".join(output)
    
    @staticmethod
    def _netmon_blacklist_list(fs, cwd, options):
        """List blacklisted addresses"""
        blacklist = NetworkMonitor._blacklist
        
        if not blacklist:
            return "No blacklisted addresses found"
        
        # Format output
        output = [f"Blacklisted Addresses: {len(blacklist)}"]
        
        for addr in sorted(blacklist):
            output.append(addr)
        
        return "\n".join(output)
    
    @staticmethod
    def _netmon_blacklist_add(fs, cwd, options):
        """Add address to blacklist"""
        if not options:
            return "netmon blacklist add: address required"
        
        addr = options[0]
        
        # Add to blacklist
        success, message = NetworkMonitor.add_to_blacklist(addr)
        
        return message
    
    @staticmethod
    def _netmon_blacklist_remove(fs, cwd, options):
        """Remove address from blacklist"""
        if not options:
            return "netmon blacklist remove: address required"
        
        addr = options[0]
        
        # Remove from blacklist
        success, message = NetworkMonitor.remove_from_blacklist(addr)
        
        return message
    
    @staticmethod
    def _netmon_blacklist_check(fs, cwd, options):
        """Check if address is blacklisted"""
        if not options:
            return "netmon blacklist check: address required"
        
        addr = options[0]
        
        # Check if blacklisted
        is_blacklisted = NetworkMonitor.is_blacklisted(addr)
        
        if is_blacklisted:
            return f"Address {addr} is blacklisted"
        else:
            return f"Address {addr} is not blacklisted"
    
    @staticmethod
    def _netmon_whitelist_list(fs, cwd, options):
        """List whitelisted addresses"""
        whitelist = NetworkMonitor._whitelist
        
        if not whitelist:
            return "No whitelisted addresses found"
        
        # Format output
        output = [f"Whitelisted Addresses: {len(whitelist)}"]
        
        for addr in sorted(whitelist):
            output.append(addr)
        
        return "\n".join(output)
    
    @staticmethod
    def _netmon_whitelist_add(fs, cwd, options):
        """Add address to whitelist"""
        if not options:
            return "netmon whitelist add: address required"
        
        addr = options[0]
        
        # Add to whitelist
        success, message = NetworkMonitor.add_to_whitelist(addr)
        
        return message
    
    @staticmethod
    def _netmon_whitelist_remove(fs, cwd, options):
        """Remove address from whitelist"""
        if not options:
            return "netmon whitelist remove: address required"
        
        addr = options[0]
        
        # Remove from whitelist
        success, message = NetworkMonitor.remove_from_whitelist(addr)
        
        return message
    
    @staticmethod
    def _netmon_whitelist_check(fs, cwd, options):
        """Check if address is whitelisted"""
        if not options:
            return "netmon whitelist check: address required"
        
        addr = options[0]
        
        # Check if whitelisted
        is_whitelisted = NetworkMonitor.is_whitelisted(addr)
        
        if is_whitelisted:
            return f"Address {addr} is whitelisted"
        else:
            return f"Address {addr} is not whitelisted"
    
    @staticmethod
    def _netmon_host_tag_add(fs, cwd, options):
        """Add tag to host"""
        if len(options) < 2:
            return "netmon host tag add: host address and tag required"
        
        addr = options[0]
        tag = options[1]
        
        # Add tag
        success, message = NetworkMonitor.add_host_tag(addr, tag)
        
        return message
    
    @staticmethod
    def _netmon_host_tag_remove(fs, cwd, options):
        """Remove tag from host"""
        if len(options) < 2:
            return "netmon host tag remove: host address and tag required"
        
        addr = options[0]
        tag = options[1]
        
        # Remove tag
        success, message = NetworkMonitor.remove_host_tag(addr, tag)
        
        return message
    
    @staticmethod
    def _netmon_set(fs, cwd, options):
        """Set configuration option"""
        if len(options) < 2:
            return "netmon set: option and value required"
        
        option = options[0]
        value = options[1]
        
        if option == "interval":
            try:
                interval = int(value)
                success, message = NetworkMonitor.set_check_interval(interval)
                return message
            except ValueError:
                return f"netmon set: invalid interval: {value}"
        elif option == "max_rate":
            try:
                rate = int(value)
                success, message = NetworkMonitor.set_max_rate(rate)
                return message
            except ValueError:
                return f"netmon set: invalid rate: {value}"
        elif option == "max_connections":
            try:
                max_connections = int(value)
                NetworkMonitor._netmon_config['max_connections'] = max_connections
                return f"Maximum connections set to {max_connections}"
            except ValueError:
                return f"netmon set: invalid max_connections: {value}"
        elif option == "alert_on_blacklist":
            if value.lower() in ["yes", "true", "1", "on"]:
                NetworkMonitor._netmon_config['alert_on_blacklist'] = True
                return "Alert on blacklisted connections: enabled"
            elif value.lower() in ["no", "false", "0", "off"]:
                NetworkMonitor._netmon_config['alert_on_blacklist'] = False
                return "Alert on blacklisted connections: disabled"
            else:
                return f"netmon set: invalid value for alert_on_blacklist: {value}"
        elif option == "alert_on_new_hosts":
            if value.lower() in ["yes", "true", "1", "on"]:
                NetworkMonitor._netmon_config['alert_on_new_hosts'] = True
                return "Alert on new hosts: enabled"
            elif value.lower() in ["no", "false", "0", "off"]:
                NetworkMonitor._netmon_config['alert_on_new_hosts'] = False
                return "Alert on new hosts: disabled"
            else:
                return f"netmon set: invalid value for alert_on_new_hosts: {value}"
        elif option == "log_file":
            NetworkMonitor._netmon_config['log_file'] = value
            return f"Log file set to {value}"
        else:
            return f"netmon set: unknown option: {option}"
    
    @staticmethod
    def _netmon_save(fs, cwd, options):
        """Save network monitor database"""
        if options:
            db_file = options[0]
            
            # Resolve relative path
            if not os.path.isabs(db_file):
                db_file = os.path.join(cwd, db_file)
        else:
            db_file = os.path.join(os.path.expanduser('~'), '.kos', 'security', 'network.json')
        
        success, message = NetworkMonitor.save_database(db_file)
        return message
    
    @staticmethod
    def _netmon_load(fs, cwd, options):
        """Load network monitor database"""
        if options:
            db_file = options[0]
            
            # Resolve relative path
            if not os.path.isabs(db_file):
                db_file = os.path.join(cwd, db_file)
        else:
            db_file = os.path.join(os.path.expanduser('~'), '.kos', 'security', 'network.json')
        
        success, message = NetworkMonitor.load_database(db_file)
        return message

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("netmon", NetworkMonitorUtilities.do_netmon)

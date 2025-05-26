#!/usr/bin/env python3
"""
KOS netctl - Network Management Command

This command provides comprehensive network management capabilities:
- Interface configuration and management
- Firewall rule management
- Routing table configuration
- DNS configuration
- Network service discovery
"""

import argparse
import os
import sys
import time
import json
import ipaddress
from typing import List, Dict, Any, Optional

from ...core import network
from ...core.network import NetworkInterfaceType, NetworkInterfaceState, FirewallAction
from ...utils import formatting, logging

# Initialize the network subsystem
network.initialize()

def format_bytes(bytes_value):
    """Format bytes into human-readable form"""
    if bytes_value < 1024:
        return f"{bytes_value} B"
    elif bytes_value < 1024 * 1024:
        return f"{bytes_value / 1024:.1f} KB"
    elif bytes_value < 1024 * 1024 * 1024:
        return f"{bytes_value / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_value / (1024 * 1024 * 1024):.1f} GB"

def list_interfaces(args):
    """List all network interfaces"""
    interfaces = network.list_interfaces()
    
    if not interfaces:
        print("No network interfaces found")
        return 0
    
    # Format as a table
    headers = ["Name", "Type", "IPv4 Address", "State", "MAC Address"]
    
    if args.verbose:
        headers.extend(["RX", "TX", "MTU"])
    
    rows = []
    
    for iface in interfaces:
        row = [
            iface['name'],
            iface['type'],
            f"{iface['ipv4_address']}/{iface['ipv4_netmask']}",
            iface['state'],
            iface['mac_address']
        ]
        
        if args.verbose:
            row.extend([
                format_bytes(iface['metrics']['rx_bytes']),
                format_bytes(iface['metrics']['tx_bytes']),
                str(iface['mtu'])
            ])
        
        rows.append(row)
    
    print(formatting.format_table(headers, rows))
    return 0

def show_interface(args):
    """Show details for a specific interface"""
    iface = network.get_interface(args.name)
    
    if not iface:
        print(f"Interface not found: {args.name}", file=sys.stderr)
        return 1
    
    print(f"Interface: {iface['name']} ({iface['type']})")
    print(f"  State: {iface['state']}")
    print(f"  IPv4 Address: {iface['ipv4_address']}/{iface['ipv4_netmask']}")
    print(f"  MAC Address: {iface['mac_address']}")
    print(f"  MTU: {iface['mtu']}")
    print(f"  Virtual: {'yes' if iface['virtual'] else 'no'}")
    print(f"  Managed: {'yes' if iface['managed'] else 'no'}")
    
    # Type-specific information
    if iface['type'] == NetworkInterfaceType.BRIDGE:
        print(f"  Bridge Interfaces: {', '.join(iface.get('bridge_interfaces', []))}")
    elif iface['type'] == NetworkInterfaceType.VLAN:
        print(f"  VLAN ID: {iface.get('vlan_id')}")
        print(f"  Parent Interface: {iface.get('parent_interface')}")
    
    # Show metrics
    print("\nMetrics:")
    print(f"  RX: {format_bytes(iface['metrics']['rx_bytes'])} ({iface['metrics']['rx_packets']} packets)")
    print(f"  TX: {format_bytes(iface['metrics']['tx_bytes'])} ({iface['metrics']['tx_packets']} packets)")
    print(f"  Errors: {iface['metrics']['rx_errors']} rx, {iface['metrics']['tx_errors']} tx")
    
    return 0

def create_interface(args):
    """Create a new virtual interface"""
    # Validate IP address and netmask if provided
    if args.ipv4_address and args.ipv4_netmask:
        try:
            ipaddress.IPv4Address(args.ipv4_address)
            ipaddress.IPv4Address(args.ipv4_netmask)
        except ValueError as e:
            print(f"Invalid IP address or netmask: {e}", file=sys.stderr)
            return 1
    
    # Additional parameters based on interface type
    kwargs = {
        'mtu': args.mtu
    }
    
    if args.type == NetworkInterfaceType.BRIDGE:
        kwargs['bridge_interfaces'] = args.bridge_interfaces or []
    elif args.type == NetworkInterfaceType.VLAN:
        if not args.vlan_id:
            print("VLAN ID is required for VLAN interfaces", file=sys.stderr)
            return 1
        if not args.parent_interface:
            print("Parent interface is required for VLAN interfaces", file=sys.stderr)
            return 1
        
        kwargs['vlan_id'] = args.vlan_id
        kwargs['parent_interface'] = args.parent_interface
    elif args.type in (NetworkInterfaceType.TUN, NetworkInterfaceType.TAP):
        kwargs['owner'] = args.owner
        kwargs['group'] = args.group
        kwargs['persistent'] = args.persistent
    
    # Create the interface
    if network.create_interface(
        args.name,
        args.type,
        args.ipv4_address,
        args.ipv4_netmask,
        **kwargs
    ):
        print(f"Created interface: {args.name}")
        
        # Set interface state if requested
        if args.up:
            network.set_interface_state(args.name, NetworkInterfaceState.UP)
            print(f"Interface {args.name} is up")
        
        return 0
    else:
        print(f"Failed to create interface: {args.name}", file=sys.stderr)
        return 1

def delete_interface(args):
    """Delete a virtual interface"""
    if network.delete_interface(args.name):
        print(f"Deleted interface: {args.name}")
        return 0
    else:
        print(f"Failed to delete interface: {args.name}", file=sys.stderr)
        return 1

def set_interface_address(args):
    """Set interface IP address"""
    # Validate IP address and netmask
    try:
        ipaddress.IPv4Address(args.ipv4_address)
        ipaddress.IPv4Address(args.ipv4_netmask)
    except ValueError as e:
        print(f"Invalid IP address or netmask: {e}", file=sys.stderr)
        return 1
    
    if network.set_interface_address(args.name, args.ipv4_address, args.ipv4_netmask):
        print(f"Set interface {args.name} address to {args.ipv4_address}/{args.ipv4_netmask}")
        return 0
    else:
        print(f"Failed to set interface address", file=sys.stderr)
        return 1

def set_interface_state(args):
    """Set interface state (up/down)"""
    state = NetworkInterfaceState.UP if args.up else NetworkInterfaceState.DOWN
    
    if network.set_interface_state(args.name, state):
        print(f"Set interface {args.name} state to {state}")
        return 0
    else:
        print(f"Failed to set interface state", file=sys.stderr)
        return 1

def list_firewall_rules(args):
    """List all firewall rules"""
    rules = network.list_firewall_rules()
    
    if not rules:
        print("No firewall rules found")
        return 0
    
    # Format as a table
    headers = ["#", "Action", "Protocol", "Source", "Destination", "Ports"]
    rows = []
    
    for i, rule in enumerate(rules):
        source = rule.get('source', 'any')
        destination = rule.get('destination', 'any')
        ports = rule.get('port', 'any')
        if isinstance(ports, list):
            ports = ','.join(map(str, ports))
        
        rows.append([
            str(i),
            rule['action'],
            rule['protocol'],
            source,
            destination,
            ports
        ])
    
    print(formatting.format_table(headers, rows))
    return 0

def add_firewall_rule(args):
    """Add a firewall rule"""
    # Create rule dictionary
    rule = {
        'action': args.action,
        'protocol': args.protocol
    }
    
    # Add source if specified
    if args.source and args.source != 'any':
        rule['source'] = args.source
    
    # Add destination if specified
    if args.destination and args.destination != 'any':
        rule['destination'] = args.destination
    
    # Add port if specified
    if args.port and args.port != 'any':
        try:
            if '-' in args.port:
                # Port range
                start, end = map(int, args.port.split('-'))
                rule['port'] = [start, end]
            elif ',' in args.port:
                # Multiple ports
                rule['port'] = list(map(int, args.port.split(',')))
            else:
                # Single port
                rule['port'] = int(args.port)
        except ValueError:
            print(f"Invalid port specification: {args.port}", file=sys.stderr)
            return 1
    
    # Add rule
    if network.add_firewall_rule(rule):
        print(f"Added firewall rule: {args.action} {args.protocol} " +
             f"{args.source} -> {args.destination}")
        return 0
    else:
        print(f"Failed to add firewall rule", file=sys.stderr)
        return 1

def remove_firewall_rule(args):
    """Remove a firewall rule"""
    try:
        index = int(args.index)
    except ValueError:
        print(f"Invalid rule index: {args.index}", file=sys.stderr)
        return 1
    
    if network.remove_firewall_rule(index):
        print(f"Removed firewall rule #{args.index}")
        return 0
    else:
        print(f"Failed to remove firewall rule", file=sys.stderr)
        return 1

def list_routes(args):
    """List all routes"""
    routes = network.list_routes()
    
    if not routes:
        print("No routes found")
        return 0
    
    # Format as a table
    headers = ["Destination", "Gateway", "Interface", "Metric"]
    rows = []
    
    for route in routes:
        rows.append([
            route['destination'],
            route['gateway'] or 'direct',
            route['interface'] or 'any',
            str(route['metric'])
        ])
    
    print(formatting.format_table(headers, rows))
    return 0

def add_route(args):
    """Add a route"""
    if network.add_route(
        args.destination,
        args.gateway,
        args.interface,
        args.metric
    ):
        print(f"Added route to {args.destination} via {args.gateway or 'direct'}")
        return 0
    else:
        print(f"Failed to add route", file=sys.stderr)
        return 1

def remove_route(args):
    """Remove a route"""
    if network.remove_route(args.destination):
        print(f"Removed route to {args.destination}")
        return 0
    else:
        print(f"Failed to remove route", file=sys.stderr)
        return 1

def list_dns_servers(args):
    """List all DNS servers"""
    servers = network.list_dns_servers()
    
    if not servers:
        print("No DNS servers configured")
        return 0
    
    print("DNS Servers:")
    for i, server in enumerate(servers):
        print(f"  {i+1}. {server}")
    
    return 0

def add_dns_server(args):
    """Add a DNS server"""
    if network.add_dns_server(args.server):
        print(f"Added DNS server: {args.server}")
        return 0
    else:
        print(f"Failed to add DNS server", file=sys.stderr)
        return 1

def remove_dns_server(args):
    """Remove a DNS server"""
    if network.remove_dns_server(args.server):
        print(f"Removed DNS server: {args.server}")
        return 0
    else:
        print(f"Failed to remove DNS server", file=sys.stderr)
        return 1

def resolve_hostname(args):
    """Resolve a hostname to IP addresses"""
    addresses = network.resolve_hostname(args.hostname, not args.no_cache)
    
    if addresses:
        print(f"Hostname: {args.hostname}")
        print("IP Addresses:")
        for addr in addresses:
            print(f"  {addr}")
        return 0
    else:
        print(f"Failed to resolve hostname: {args.hostname}", file=sys.stderr)
        return 1

def list_network_services(args):
    """List all registered network services"""
    services = network.list_network_services()
    
    if not services:
        print("No network services registered")
        return 0
    
    # Format as a table
    headers = ["Name", "Protocol", "Port", "State", "PID"]
    rows = []
    
    for service in services:
        rows.append([
            service['name'],
            service['protocol'],
            str(service['port']),
            service.get('state', 'UNKNOWN').lower(),
            str(service.get('pid', 'n/a'))
        ])
    
    print(formatting.format_table(headers, rows))
    return 0

def register_service(args):
    """Register a network service"""
    if network.register_network_service(
        args.name,
        args.port,
        args.protocol,
        args.description
    ):
        print(f"Registered network service: {args.name} ({args.protocol}/{args.port})")
        return 0
    else:
        print(f"Failed to register network service", file=sys.stderr)
        return 1

def unregister_service(args):
    """Unregister a network service"""
    if network.unregister_network_service(args.name):
        print(f"Unregistered network service: {args.name}")
        return 0
    else:
        print(f"Failed to unregister network service", file=sys.stderr)
        return 1

def main(args=None):
    """Main entry point"""
    parser = argparse.ArgumentParser(description="KOS netctl - Network Management Command")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Interface commands
    iface_parser = subparsers.add_parser("interface", help="Interface management")
    iface_subparsers = iface_parser.add_subparsers(dest="iface_command", help="Interface command")
    
    # List interfaces
    list_iface_parser = iface_subparsers.add_parser("list", help="List interfaces")
    list_iface_parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed information")
    list_iface_parser.set_defaults(func=list_interfaces)
    
    # Show interface
    show_iface_parser = iface_subparsers.add_parser("show", help="Show interface details")
    show_iface_parser.add_argument("name", help="Interface name")
    show_iface_parser.set_defaults(func=show_interface)
    
    # Create interface
    create_iface_parser = iface_subparsers.add_parser("create", help="Create a virtual interface")
    create_iface_parser.add_argument("name", help="Interface name")
    create_iface_parser.add_argument("--type", "-t", required=True, 
                                    choices=[NetworkInterfaceType.BRIDGE, 
                                             NetworkInterfaceType.VLAN,
                                             NetworkInterfaceType.TUN,
                                             NetworkInterfaceType.TAP],
                                    help="Interface type")
    create_iface_parser.add_argument("--ipv4-address", "-a", help="IPv4 address")
    create_iface_parser.add_argument("--ipv4-netmask", "-n", help="IPv4 netmask")
    create_iface_parser.add_argument("--mtu", "-m", type=int, default=1500, help="MTU")
    create_iface_parser.add_argument("--up", action="store_true", help="Bring interface up")
    
    # Type-specific arguments
    create_iface_parser.add_argument("--bridge-interfaces", nargs="+", help="Interfaces to bridge (for bridge type)")
    create_iface_parser.add_argument("--vlan-id", type=int, help="VLAN ID (for vlan type)")
    create_iface_parser.add_argument("--parent-interface", help="Parent interface (for vlan type)")
    create_iface_parser.add_argument("--owner", help="Owner (for tun/tap type)")
    create_iface_parser.add_argument("--group", help="Group (for tun/tap type)")
    create_iface_parser.add_argument("--persistent", action="store_true", help="Persistent (for tun/tap type)")
    
    create_iface_parser.set_defaults(func=create_interface)
    
    # Delete interface
    delete_iface_parser = iface_subparsers.add_parser("delete", help="Delete a virtual interface")
    delete_iface_parser.add_argument("name", help="Interface name")
    delete_iface_parser.set_defaults(func=delete_interface)
    
    # Set interface address
    addr_iface_parser = iface_subparsers.add_parser("address", help="Set interface address")
    addr_iface_parser.add_argument("name", help="Interface name")
    addr_iface_parser.add_argument("ipv4_address", help="IPv4 address")
    addr_iface_parser.add_argument("ipv4_netmask", help="IPv4 netmask")
    addr_iface_parser.set_defaults(func=set_interface_address)
    
    # Set interface state
    state_iface_parser = iface_subparsers.add_parser("state", help="Set interface state")
    state_iface_parser.add_argument("name", help="Interface name")
    state_iface_parser.add_argument("--up", action="store_true", help="Bring interface up")
    state_iface_parser.add_argument("--down", action="store_true", help="Bring interface down")
    state_iface_parser.set_defaults(func=set_interface_state)
    
    # Firewall commands
    fw_parser = subparsers.add_parser("firewall", help="Firewall management")
    fw_subparsers = fw_parser.add_subparsers(dest="fw_command", help="Firewall command")
    
    # List firewall rules
    list_fw_parser = fw_subparsers.add_parser("list", help="List firewall rules")
    list_fw_parser.set_defaults(func=list_firewall_rules)
    
    # Add firewall rule
    add_fw_parser = fw_subparsers.add_parser("add", help="Add a firewall rule")
    add_fw_parser.add_argument("--action", "-a", required=True,
                              choices=[FirewallAction.ACCEPT, 
                                       FirewallAction.REJECT,
                                       FirewallAction.DROP,
                                       FirewallAction.LOG],
                              help="Rule action")
    add_fw_parser.add_argument("--protocol", "-p", required=True,
                              choices=["tcp", "udp", "icmp", "any"],
                              help="Protocol")
    add_fw_parser.add_argument("--source", "-s", default="any",
                              help="Source address (IP or network)")
    add_fw_parser.add_argument("--destination", "-d", default="any",
                              help="Destination address (IP or network)")
    add_fw_parser.add_argument("--port", default="any",
                              help="Port(s) (single, range, or comma-separated)")
    add_fw_parser.set_defaults(func=add_firewall_rule)
    
    # Remove firewall rule
    del_fw_parser = fw_subparsers.add_parser("delete", help="Delete a firewall rule")
    del_fw_parser.add_argument("index", help="Rule index")
    del_fw_parser.set_defaults(func=remove_firewall_rule)
    
    # Route commands
    route_parser = subparsers.add_parser("route", help="Route management")
    route_subparsers = route_parser.add_subparsers(dest="route_command", help="Route command")
    
    # List routes
    list_route_parser = route_subparsers.add_parser("list", help="List routes")
    list_route_parser.set_defaults(func=list_routes)
    
    # Add route
    add_route_parser = route_subparsers.add_parser("add", help="Add a route")
    add_route_parser.add_argument("destination", help="Destination network (CIDR notation)")
    add_route_parser.add_argument("--gateway", "-g", help="Gateway IP address")
    add_route_parser.add_argument("--interface", "-i", help="Interface")
    add_route_parser.add_argument("--metric", "-m", type=int, default=0, help="Metric")
    add_route_parser.set_defaults(func=add_route)
    
    # Delete route
    del_route_parser = route_subparsers.add_parser("delete", help="Delete a route")
    del_route_parser.add_argument("destination", help="Destination network (CIDR notation)")
    del_route_parser.set_defaults(func=remove_route)
    
    # DNS commands
    dns_parser = subparsers.add_parser("dns", help="DNS management")
    dns_subparsers = dns_parser.add_subparsers(dest="dns_command", help="DNS command")
    
    # List DNS servers
    list_dns_parser = dns_subparsers.add_parser("list", help="List DNS servers")
    list_dns_parser.set_defaults(func=list_dns_servers)
    
    # Add DNS server
    add_dns_parser = dns_subparsers.add_parser("add", help="Add a DNS server")
    add_dns_parser.add_argument("server", help="DNS server IP address")
    add_dns_parser.set_defaults(func=add_dns_server)
    
    # Remove DNS server
    del_dns_parser = dns_subparsers.add_parser("delete", help="Delete a DNS server")
    del_dns_parser.add_argument("server", help="DNS server IP address")
    del_dns_parser.set_defaults(func=remove_dns_server)
    
    # Resolve hostname
    resolve_parser = dns_subparsers.add_parser("resolve", help="Resolve a hostname")
    resolve_parser.add_argument("hostname", help="Hostname to resolve")
    resolve_parser.add_argument("--no-cache", action="store_true", help="Don't use DNS cache")
    resolve_parser.set_defaults(func=resolve_hostname)
    
    # Service commands
    service_parser = subparsers.add_parser("service", help="Network service management")
    service_subparsers = service_parser.add_subparsers(dest="service_command", help="Service command")
    
    # List services
    list_svc_parser = service_subparsers.add_parser("list", help="List network services")
    list_svc_parser.set_defaults(func=list_network_services)
    
    # Register service
    reg_svc_parser = service_subparsers.add_parser("register", help="Register a network service")
    reg_svc_parser.add_argument("name", help="Service name")
    reg_svc_parser.add_argument("--port", "-p", type=int, required=True, help="Port number")
    reg_svc_parser.add_argument("--protocol", "-t", default="tcp",
                               choices=["tcp", "udp", "http", "https"],
                               help="Protocol")
    reg_svc_parser.add_argument("--description", "-d", help="Service description")
    reg_svc_parser.set_defaults(func=register_service)
    
    # Unregister service
    unreg_svc_parser = service_subparsers.add_parser("unregister", help="Unregister a network service")
    unreg_svc_parser.add_argument("name", help="Service name")
    unreg_svc_parser.set_defaults(func=unregister_service)
    
    # Parse arguments
    args = parser.parse_args(args)
    
    # Special case for interface command with no subcommand
    if args.command == "interface" and not args.iface_command:
        return list_interfaces(argparse.Namespace(verbose=False))
    
    # Special case for firewall command with no subcommand
    if args.command == "firewall" and not args.fw_command:
        return list_firewall_rules(argparse.Namespace())
    
    # Special case for route command with no subcommand
    if args.command == "route" and not args.route_command:
        return list_routes(argparse.Namespace())
    
    # Special case for dns command with no subcommand
    if args.command == "dns" and not args.dns_command:
        return list_dns_servers(argparse.Namespace())
    
    # Special case for service command with no subcommand
    if args.command == "service" and not args.service_command:
        return list_network_services(argparse.Namespace())
    
    # Default command is to list interfaces
    if not args.command or not hasattr(args, 'func'):
        return list_interfaces(argparse.Namespace(verbose=False))
    
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())


"""
Firewall Management Utilities for KOS Shell

This module provides firewall management commands for KOS,
with an interface similar to iptables in Linux.
"""

import os
import sys
import time
import logging
import json
import shlex
from typing import Dict, List, Any, Optional, Union

# Import KOS components
from kos.network.firewall import FirewallManager, NAT, TABLES

# Lazy import for klayer to avoid circular import issues
klayer = None
def get_klayer():
    global klayer
    if klayer is None:
        try:
            from kos.layer import klayer as _klayer
            klayer = _klayer
        except ImportError:
            klayer = None
    return klayer

# Set up logging
logger = logging.getLogger('KOS.shell.commands.firewall_manager')

class FirewallUtilities:
    """Firewall management commands for KOS shell"""
    
    @staticmethod
    def do_firewall(fs, cwd, arg):
        """
        Manage KOS firewall
        
        Usage: firewall COMMAND [options]
        
        Commands:
          list [table] [chain]         List firewall rules
          add [options]                Add a firewall rule
          delete ID                    Delete a firewall rule
          clear table chain            Clear all rules from a chain
          save [file]                  Save firewall rules to file
          load [file]                  Load firewall rules from file
          port-forward [options]       Add a port forwarding rule
          masquerade [options]         Add a masquerade rule
        """
        args = shlex.split(arg)
        
        if not args:
            return FirewallUtilities.do_firewall.__doc__
        
        command = args[0]
        options = args[1:]
        
        # Process commands
        if command == "list":
            return FirewallUtilities._firewall_list(options)
        elif command == "add":
            return FirewallUtilities._firewall_add(options)
        elif command == "delete":
            return FirewallUtilities._firewall_delete(options)
        elif command == "clear":
            return FirewallUtilities._firewall_clear(options)
        elif command == "save":
            return FirewallUtilities._firewall_save(options)
        elif command == "load":
            return FirewallUtilities._firewall_load(options)
        elif command == "port-forward":
            return FirewallUtilities._firewall_port_forward(options)
        elif command == "masquerade":
            return FirewallUtilities._firewall_masquerade(options)
        else:
            return f"firewall: '{command}' is not a firewall command.\nSee 'firewall --help'"
    
    @staticmethod
    def do_iptables(fs, cwd, arg):
        """
        Manage firewall rules (iptables-like interface)
        
        Usage: iptables [options]
        
        Options:
          -t, --table TABLE    Table to use (filter, nat, mangle)
          -L, --list [CHAIN]   List rules in chain or all chains
          -A, --append CHAIN   Append rule to chain
          -D, --delete RULE    Delete rule by number or specification
          -F, --flush [CHAIN]  Flush chain or all chains
          -p, --protocol PROTO Protocol (tcp, udp, icmp, all)
          -s, --source ADDR    Source address
          -d, --dest ADDR      Destination address
          --sport PORT         Source port
          --dport PORT         Destination port
          -i, --in-interface I Input interface
          -o, --out-interface I Output interface
          -j, --jump TARGET    Target for rule (ACCEPT, DROP, REJECT, etc.)
          -m, --match MATCH    Match module
          --comment TEXT       Add comment to rule
        """
        # Process iptables arguments
        args = shlex.split(arg)
        
        # Default values
        table = "filter"
        command = None
        chain = None
        protocol = None
        source = None
        destination = None
        source_port = None
        destination_port = None
        interface_in = None
        interface_out = None
        action = None
        comment = None
        rule_num = None
        
        i = 0
        while i < len(args):
            if args[i] in ["-t", "--table"]:
                if i + 1 < len(args):
                    table = args[i+1]
                    i += 2
                else:
                    return "iptables: option requires an argument -- '-t'"
            elif args[i] in ["-L", "--list"]:
                command = "list"
                if i + 1 < len(args) and not args[i+1].startswith("-"):
                    chain = args[i+1]
                    i += 2
                else:
                    i += 1
            elif args[i] in ["-A", "--append"]:
                command = "add"
                if i + 1 < len(args):
                    chain = args[i+1]
                    i += 2
                else:
                    return "iptables: option requires an argument -- '-A'"
            elif args[i] in ["-D", "--delete"]:
                command = "delete"
                if i + 1 < len(args):
                    if args[i+1].isdigit():
                        rule_num = int(args[i+1])
                    else:
                        chain = args[i+1]
                    i += 2
                else:
                    return "iptables: option requires an argument -- '-D'"
            elif args[i] in ["-F", "--flush"]:
                command = "clear"
                if i + 1 < len(args) and not args[i+1].startswith("-"):
                    chain = args[i+1]
                    i += 2
                else:
                    i += 1
            elif args[i] in ["-p", "--protocol"]:
                if i + 1 < len(args):
                    protocol = args[i+1]
                    i += 2
                else:
                    return "iptables: option requires an argument -- '-p'"
            elif args[i] in ["-s", "--source"]:
                if i + 1 < len(args):
                    source = args[i+1]
                    i += 2
                else:
                    return "iptables: option requires an argument -- '-s'"
            elif args[i] in ["-d", "--dest"]:
                if i + 1 < len(args):
                    destination = args[i+1]
                    i += 2
                else:
                    return "iptables: option requires an argument -- '-d'"
            elif args[i] == "--sport":
                if i + 1 < len(args):
                    source_port = args[i+1]
                    i += 2
                else:
                    return "iptables: option requires an argument -- '--sport'"
            elif args[i] == "--dport":
                if i + 1 < len(args):
                    destination_port = args[i+1]
                    i += 2
                else:
                    return "iptables: option requires an argument -- '--dport'"
            elif args[i] in ["-i", "--in-interface"]:
                if i + 1 < len(args):
                    interface_in = args[i+1]
                    i += 2
                else:
                    return "iptables: option requires an argument -- '-i'"
            elif args[i] in ["-o", "--out-interface"]:
                if i + 1 < len(args):
                    interface_out = args[i+1]
                    i += 2
                else:
                    return "iptables: option requires an argument -- '-o'"
            elif args[i] in ["-j", "--jump"]:
                if i + 1 < len(args):
                    action = args[i+1]
                    i += 2
                else:
                    return "iptables: option requires an argument -- '-j'"
            elif args[i] == "--comment":
                if i + 1 < len(args):
                    comment = args[i+1]
                    i += 2
                else:
                    return "iptables: option requires an argument -- '--comment'"
            else:
                i += 1
        
        # Validate and process command
        if not command:
            return "iptables: no command specified"
        
        if command == "list":
            return FirewallUtilities._iptables_list(table, chain)
        elif command == "add":
            if not chain:
                return "iptables: no chain specified"
            
            return FirewallUtilities._iptables_add(
                table=table,
                chain=chain,
                protocol=protocol,
                source=source,
                destination=destination,
                source_port=source_port,
                destination_port=destination_port,
                interface_in=interface_in,
                interface_out=interface_out,
                action=action,
                comment=comment
            )
        elif command == "delete":
            if rule_num is not None:
                return FirewallUtilities._iptables_delete_by_num(table, chain, rule_num)
            elif chain:
                return FirewallUtilities._iptables_delete_by_spec(
                    table=table,
                    chain=chain,
                    protocol=protocol,
                    source=source,
                    destination=destination,
                    source_port=source_port,
                    destination_port=destination_port,
                    interface_in=interface_in,
                    interface_out=interface_out,
                    action=action
                )
            else:
                return "iptables: no rule specified for deletion"
        elif command == "clear":
            if not chain:
                # Clear all chains in table
                for c in TABLES[table]['chains']:
                    FirewallManager.clear_chain(table, c)
                return f"Flushed all chains in table {table}"
            else:
                return FirewallUtilities._iptables_clear(table, chain)
        else:
            return f"iptables: command '{command}' not implemented"
    
    @staticmethod
    def _firewall_list(options):
        """List firewall rules"""
        table = None
        chain = None
        
        if options:
            table = options[0]
            if len(options) > 1:
                chain = options[1]
        
        # Get rules
        rules = FirewallManager.list_rules(table, chain)
        
        # Format output
        if not rules:
            if table and chain:
                return f"No rules in {table}/{chain}"
            elif table:
                return f"No rules in table {table}"
            else:
                return "No firewall rules defined"
        
        result = ["ID          TABLE       CHAIN       ACTION     DESCRIPTION"]
        
        for rule in rules:
            description = []
            if rule.protocol:
                description.append(f"proto={rule.protocol}")
            if rule.source:
                description.append(f"src={rule.source}")
            if rule.destination:
                description.append(f"dst={rule.destination}")
            if rule.source_port:
                description.append(f"sport={rule.source_port}")
            if rule.destination_port:
                description.append(f"dport={rule.destination_port}")
            
            result.append(f"{rule.id:<12} {rule.table:<12} {rule.chain:<12} {rule.action:<10} {' '.join(description)}")
        
        return "\n".join(result)
    
    @staticmethod
    def _firewall_add(options):
        """Add a firewall rule"""
        # Parse options
        if len(options) < 2:
            return "firewall add: chain and table are required"
        
        table = options[0]
        chain = options[1]
        rule_options = options[2:]
        
        # Parse rule options
        protocol = None
        source = None
        destination = None
        source_port = None
        destination_port = None
        interface_in = None
        interface_out = None
        action = "ACCEPT"
        comment = None
        
        i = 0
        while i < len(rule_options):
            if rule_options[i] == "--protocol":
                if i + 1 < len(rule_options):
                    protocol = rule_options[i+1]
                    i += 2
                else:
                    return "firewall add: option requires an argument -- '--protocol'"
            elif rule_options[i] == "--source":
                if i + 1 < len(rule_options):
                    source = rule_options[i+1]
                    i += 2
                else:
                    return "firewall add: option requires an argument -- '--source'"
            elif rule_options[i] == "--destination":
                if i + 1 < len(rule_options):
                    destination = rule_options[i+1]
                    i += 2
                else:
                    return "firewall add: option requires an argument -- '--destination'"
            elif rule_options[i] == "--source-port":
                if i + 1 < len(rule_options):
                    source_port = rule_options[i+1]
                    i += 2
                else:
                    return "firewall add: option requires an argument -- '--source-port'"
            elif rule_options[i] == "--destination-port":
                if i + 1 < len(rule_options):
                    destination_port = rule_options[i+1]
                    i += 2
                else:
                    return "firewall add: option requires an argument -- '--destination-port'"
            elif rule_options[i] == "--in-interface":
                if i + 1 < len(rule_options):
                    interface_in = rule_options[i+1]
                    i += 2
                else:
                    return "firewall add: option requires an argument -- '--in-interface'"
            elif rule_options[i] == "--out-interface":
                if i + 1 < len(rule_options):
                    interface_out = rule_options[i+1]
                    i += 2
                else:
                    return "firewall add: option requires an argument -- '--out-interface'"
            elif rule_options[i] == "--action":
                if i + 1 < len(rule_options):
                    action = rule_options[i+1]
                    i += 2
                else:
                    return "firewall add: option requires an argument -- '--action'"
            elif rule_options[i] == "--comment":
                if i + 1 < len(rule_options):
                    comment = rule_options[i+1]
                    i += 2
                else:
                    return "firewall add: option requires an argument -- '--comment'"
            else:
                i += 1
        
        # Add rule
        success, message, rule = FirewallManager.add_rule(
            chain=chain,
            table=table,
            protocol=protocol,
            source=source,
            destination=destination,
            source_port=source_port,
            destination_port=destination_port,
            interface_in=interface_in,
            interface_out=interface_out,
            action=action,
            comment=comment
        )
        
        if not success:
            return f"firewall add: {message}"
        
        return f"Rule added: {rule.id}"
    
    @staticmethod
    def _firewall_delete(options):
        """Delete a firewall rule"""
        if not options:
            return "firewall delete: rule ID is required"
        
        rule_id = options[0]
        
        # Delete rule
        success, message = FirewallManager.delete_rule(rule_id)
        
        if not success:
            return f"firewall delete: {message}"
        
        return message
    
    @staticmethod
    def _firewall_clear(options):
        """Clear all rules from a chain"""
        if len(options) < 2:
            return "firewall clear: table and chain are required"
        
        table = options[0]
        chain = options[1]
        
        # Clear chain
        success, message = FirewallManager.clear_chain(table, chain)
        
        if not success:
            return f"firewall clear: {message}"
        
        return message
    
    @staticmethod
    def _firewall_save(options):
        """Save firewall rules to file"""
        filepath = os.path.join(os.path.expanduser('~'), '.kos', 'firewall', 'rules.json')
        
        if options:
            filepath = options[0]
        
        # Save rules
        success, message = FirewallManager.save_rules(filepath)
        
        if not success:
            return f"firewall save: {message}"
        
        return message
    
    @staticmethod
    def _firewall_load(options):
        """Load firewall rules from file"""
        filepath = os.path.join(os.path.expanduser('~'), '.kos', 'firewall', 'rules.json')
        
        if options:
            filepath = options[0]
        
        # Load rules
        success, message = FirewallManager.load_rules(filepath)
        
        if not success:
            return f"firewall load: {message}"
        
        return message
    
    @staticmethod
    def _firewall_port_forward(options):
        """Add a port forwarding rule"""
        # Parse options
        if len(options) < 3:
            return "firewall port-forward: protocol, external port, and destination are required"
        
        protocol = options[0]
        external_port = options[1]
        destination = options[2]
        
        # Parse additional options
        destination_port = None
        interface = None
        comment = None
        
        if len(options) > 3:
            destination_port = options[3]
        
        i = 4
        while i < len(options):
            if options[i] == "--interface":
                if i + 1 < len(options):
                    interface = options[i+1]
                    i += 2
                else:
                    return "firewall port-forward: option requires an argument -- '--interface'"
            elif options[i] == "--comment":
                if i + 1 < len(options):
                    comment = options[i+1]
                    i += 2
                else:
                    return "firewall port-forward: option requires an argument -- '--comment'"
            else:
                i += 1
        
        # Add port forwarding rule
        try:
            ext_port = int(external_port)
            dst_port = int(destination_port) if destination_port else None
            
            success, message, rule = NAT.add_port_forward(
                protocol=protocol,
                external_port=ext_port,
                destination=destination,
                destination_port=dst_port,
                interface=interface,
                comment=comment
            )
            
            if not success:
                return f"firewall port-forward: {message}"
            
            return f"Port forwarding rule added: {rule.id}"
        except ValueError:
            return f"firewall port-forward: invalid port number: {external_port}"
    
    @staticmethod
    def _firewall_masquerade(options):
        """Add a masquerade rule"""
        # Parse options
        source_network = None
        interface = None
        comment = None
        
        i = 0
        while i < len(options):
            if options[i] == "--source":
                if i + 1 < len(options):
                    source_network = options[i+1]
                    i += 2
                else:
                    return "firewall masquerade: option requires an argument -- '--source'"
            elif options[i] == "--interface":
                if i + 1 < len(options):
                    interface = options[i+1]
                    i += 2
                else:
                    return "firewall masquerade: option requires an argument -- '--interface'"
            elif options[i] == "--comment":
                if i + 1 < len(options):
                    comment = options[i+1]
                    i += 2
                else:
                    return "firewall masquerade: option requires an argument -- '--comment'"
            else:
                i += 1
        
        # Add masquerade rule
        success, message, rule = NAT.add_masquerade(
            source_network=source_network,
            interface_out=interface,
            comment=comment
        )
        
        if not success:
            return f"firewall masquerade: {message}"
        
        return f"Masquerade rule added: {rule.id}"
    
    @staticmethod
    def _iptables_list(table, chain):
        """List firewall rules in iptables format"""
        # Get rules
        rules = FirewallManager.list_rules(table, chain)
        
        # Format output
        result = []
        
        if not chain:
            # Show all chains in table
            for chain_name in TABLES[table]['chains']:
                chain_rules = [r for r in rules if r.chain == chain_name]
                result.append(f"Chain {chain_name} (policy ACCEPT)")
                
                if chain_rules:
                    result.append("target     prot opt source               destination")
                    for rule in chain_rules:
                        target = rule.action
                        prot = rule.protocol or "all"
                        src = rule.source or "0.0.0.0/0"
                        dst = rule.destination or "0.0.0.0/0"
                        extras = []
                        
                        if rule.source_port:
                            extras.append(f"spt:{rule.source_port}")
                        if rule.destination_port:
                            extras.append(f"dpt:{rule.destination_port}")
                        if rule.interface_in:
                            extras.append(f"in:{rule.interface_in}")
                        if rule.interface_out:
                            extras.append(f"out:{rule.interface_out}")
                        if rule.comment:
                            extras.append(f"/* {rule.comment} */")
                        
                        extra_str = " ".join(extras)
                        result.append(f"{target:<10} {prot:<5} --  {src:<20} {dst:<20} {extra_str}")
                else:
                    result.append("No rules defined")
                
                result.append("")
        else:
            # Show specific chain
            chain_rules = [r for r in rules if r.chain == chain]
            result.append(f"Chain {chain} (policy ACCEPT)")
            
            if chain_rules:
                result.append("target     prot opt source               destination")
                for rule in chain_rules:
                    target = rule.action
                    prot = rule.protocol or "all"
                    src = rule.source or "0.0.0.0/0"
                    dst = rule.destination or "0.0.0.0/0"
                    extras = []
                    
                    if rule.source_port:
                        extras.append(f"spt:{rule.source_port}")
                    if rule.destination_port:
                        extras.append(f"dpt:{rule.destination_port}")
                    if rule.interface_in:
                        extras.append(f"in:{rule.interface_in}")
                    if rule.interface_out:
                        extras.append(f"out:{rule.interface_out}")
                    if rule.comment:
                        extras.append(f"/* {rule.comment} */")
                    
                    extra_str = " ".join(extras)
                    result.append(f"{target:<10} {prot:<5} --  {src:<20} {dst:<20} {extra_str}")
            else:
                result.append("No rules defined")
        
        return "\n".join(result)
    
    @staticmethod
    def _iptables_add(table, chain, protocol, source, destination, source_port, 
                     destination_port, interface_in, interface_out, action, comment):
        """Add a firewall rule (iptables format)"""
        # Add rule
        success, message, rule = FirewallManager.add_rule(
            chain=chain,
            table=table,
            protocol=protocol,
            source=source,
            destination=destination,
            source_port=source_port,
            destination_port=destination_port,
            interface_in=interface_in,
            interface_out=interface_out,
            action=action,
            comment=comment
        )
        
        if not success:
            return message
        
        return f"Rule added"
    
    @staticmethod
    def _iptables_delete_by_num(table, chain, rule_num):
        """Delete a firewall rule by number"""
        # Get rules in chain
        if chain:
            rules = [r for r in FirewallManager.list_rules(table, chain)]
        else:
            return "iptables: no chain specified for deletion"
        
        # Check if rule number is valid
        if rule_num < 1 or rule_num > len(rules):
            return f"iptables: invalid rule number {rule_num}"
        
        # Get rule ID
        rule_id = rules[rule_num - 1].id
        
        # Delete rule
        success, message = FirewallManager.delete_rule(rule_id)
        
        if not success:
            return message
        
        return f"Rule deleted"
    
    @staticmethod
    def _iptables_delete_by_spec(table, chain, protocol, source, destination, 
                                source_port, destination_port, interface_in, interface_out, action):
        """Delete a firewall rule by specification"""
        # Get rules in chain
        rules = [r for r in FirewallManager.list_rules(table, chain)]
        
        # Find matching rules
        matching_rules = []
        for rule in rules:
            if protocol and rule.protocol != protocol:
                continue
            if source and rule.source != source:
                continue
            if destination and rule.destination != destination:
                continue
            if source_port and rule.source_port != source_port:
                continue
            if destination_port and rule.destination_port != destination_port:
                continue
            if interface_in and rule.interface_in != interface_in:
                continue
            if interface_out and rule.interface_out != interface_out:
                continue
            if action and rule.action != action:
                continue
            
            matching_rules.append(rule)
        
        if not matching_rules:
            return "iptables: no matching rules found"
        
        # Delete first matching rule
        rule_id = matching_rules[0].id
        success, message = FirewallManager.delete_rule(rule_id)
        
        if not success:
            return message
        
        return f"Rule deleted"
    
    @staticmethod
    def _iptables_clear(table, chain):
        """Clear a chain"""
        # Clear chain
        success, message = FirewallManager.clear_chain(table, chain)
        
        if not success:
            return message
        
        return f"Chain {chain} flushed"

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("firewall", FirewallUtilities.do_firewall)
    shell.register_command("iptables", FirewallUtilities.do_iptables)

"""
Mandatory Access Control Utilities for KOS Shell

This module provides commands for managing the KOS MAC system,
with commands similar to SELinux and AppArmor tools.
"""

import os
import sys
import logging
import shlex
from typing import Dict, List, Any, Optional, Tuple

# Import KOS components
from kos.security.mac import MACManager, SecurityContext, PolicyRule, FileContextPattern
from kos.security.users import UserManager, GroupManager

# Set up logging
logger = logging.getLogger('KOS.shell.commands.mac_utils')

class MACUtilities:
    """MAC commands for KOS shell"""
    
    @staticmethod
    def do_getenforce(fs, cwd, arg):
        """
        Get the current MAC enforcement mode
        
        Usage: getenforce
        """
        if MACManager.is_enabled():
            return "Enforcing"
        else:
            return "Permissive"
    
    @staticmethod
    def do_setenforce(fs, cwd, arg):
        """
        Set the current MAC enforcement mode
        
        Usage: setenforce [0|1]
        
        Arguments:
          0                    Set permissive mode (policy not enforced)
          1                    Set enforcing mode (policy enforced)
        """
        args = shlex.split(arg)
        
        if not args:
            return MACUtilities.do_setenforce.__doc__
        
        mode = args[0]
        if mode == "0":
            success, message = MACManager.disable()
            return message
        elif mode == "1":
            success, message = MACManager.enable()
            return message
        else:
            return "setenforce: invalid enforcement mode. Use 0 for permissive or 1 for enforcing."
    
    @staticmethod
    def do_sestatus(fs, cwd, arg):
        """
        Show MAC status
        
        Usage: sestatus [options]
        
        Options:
          -v                   Be verbose
          -b                   Display current boolean values
        """
        args = shlex.split(arg)
        
        # Parse options
        verbose = "-v" in args
        booleans = "-b" in args
        
        # Get MAC status
        status = []
        status.append(f"MAC Status:                    {'Enabled' if MACManager.is_enabled() else 'Disabled'}")
        status.append(f"MAC Enforcement Mode:          {'Enforcing' if MACManager.is_enabled() else 'Permissive'}")
        
        # Add policy file path
        policy_file = os.path.join(os.path.expanduser('~'), '.kos', 'security', 'mac_policy.json')
        status.append(f"Policy File:                   {policy_file}")
        
        # Count policy rules
        rules = MACManager.list_policy_rules()
        status.append(f"Policy Rules:                  {len(rules)}")
        
        # Count file context patterns
        patterns = MACManager.list_file_context_patterns()
        status.append(f"File Context Patterns:         {len(patterns)}")
        
        if verbose:
            # Show process contexts
            status.append("\nProcess Contexts:")
            for pid in range(1, 10):  # Just check a few PIDs
                try:
                    context = MACManager.get_process_context(pid)
                    status.append(f"  PID {pid}: {context}")
                except:
                    pass
            
            # Show some file contexts
            status.append("\nFile Contexts:")
            important_paths = ["/bin", "/etc", "/home", "/tmp"]
            for path in important_paths:
                try:
                    context = MACManager.get_file_context(path)
                    status.append(f"  {path}: {context}")
                except:
                    pass
        
        if booleans:
            # This would display boolean values in a real SELinux system
            # We don't have booleans in our simplified MAC implementation
            status.append("\nMAC Booleans:")
            status.append("  (None defined in this implementation)")
        
        return "\n".join(status)
    
    @staticmethod
    def do_chcon(fs, cwd, arg):
        """
        Change security context of a file
        
        Usage: chcon [options] context file...
        
        Options:
          -R, --recursive      Operate on files and directories recursively
          -u, --user=USER      Set user part of security context
          -r, --role=ROLE      Set role part of security context
          -t, --type=TYPE      Set type part of security context
          -l, --level=LEVEL    Set level part of security context
        """
        args = shlex.split(arg)
        
        if len(args) < 2:
            return MACUtilities.do_chcon.__doc__
        
        # Parse options
        recursive = False
        user = None
        role = None
        type = None
        level = None
        context_str = None
        files = []
        
        i = 0
        while i < len(args):
            if args[i] in ["-R", "--recursive"]:
                recursive = True
                i += 1
            elif args[i].startswith("--user="):
                user = args[i][7:]
                i += 1
            elif args[i] == "-u" and i + 1 < len(args):
                user = args[i+1]
                i += 2
            elif args[i].startswith("--role="):
                role = args[i][7:]
                i += 1
            elif args[i] == "-r" and i + 1 < len(args):
                role = args[i+1]
                i += 2
            elif args[i].startswith("--type="):
                type = args[i][7:]
                i += 1
            elif args[i] == "-t" and i + 1 < len(args):
                type = args[i+1]
                i += 2
            elif args[i].startswith("--level="):
                level = args[i][8:]
                i += 1
            elif args[i] == "-l" and i + 1 < len(args):
                level = args[i+1]
                i += 2
            else:
                # First unprocessed arg is context, rest are files
                if context_str is None and not (user or role or type or level):
                    context_str = args[i]
                else:
                    # Resolve relative path
                    path = os.path.join(cwd, args[i]) if not os.path.isabs(args[i]) else args[i]
                    files.append(path)
                i += 1
        
        if not files:
            return "chcon: missing operand"
        
        # Create context
        context = None
        if context_str:
            context = SecurityContext.from_string(context_str)
        else:
            # Get default context for first file
            context = MACManager.get_file_context(files[0])
        
        # Apply user-specified parts
        if user:
            context.user = user
        if role:
            context.role = role
        if type:
            context.type = type
        if level:
            context.level = level
        
        # Process files
        results = []
        
        for file_path in files:
            if not os.path.exists(file_path):
                results.append(f"chcon: cannot access '{file_path}': No such file or directory")
                continue
            
            # Get file paths to process
            paths_to_process = []
            if recursive and os.path.isdir(file_path):
                for root, dirs, files in os.walk(file_path):
                    paths_to_process.append(root)
                    for name in files:
                        paths_to_process.append(os.path.join(root, name))
            else:
                paths_to_process.append(file_path)
            
            # Process each file
            for path in paths_to_process:
                success, message = MACManager.set_file_context(path, context)
                if not success:
                    results.append(f"chcon: failed to change context of {path}: {message}")
        
        if not results:
            return "Context changed successfully"
        else:
            return "\n".join(results)
    
    @staticmethod
    def do_ls_Z(fs, cwd, arg):
        """
        List files with security contexts
        
        Usage: ls -Z [options] [file...]
        
        Options:
          -l                   Use a long listing format
          -d                   List directories themselves, not their contents
          -R                   Recursive listing
        """
        args = shlex.split(arg)
        
        # Parse options
        long_format = "-l" in args
        list_dir = "-d" in args
        recursive = "-R" in args
        
        # Remove options
        files = [a for a in args if not a.startswith("-")]
        
        # Default to current directory if no files specified
        if not files:
            files = [cwd]
        
        # Process files
        output = []
        
        for file_arg in files:
            # Resolve relative path
            file_path = os.path.join(cwd, file_arg) if not os.path.isabs(file_arg) else file_arg
            
            if not os.path.exists(file_path):
                output.append(f"ls: cannot access '{file_arg}': No such file or directory")
                continue
            
            # List directory contents or file
            if os.path.isdir(file_path) and not list_dir:
                if len(files) > 1:
                    output.append(f"\n{file_arg}:")
                
                # Get directory contents
                entries = os.listdir(file_path)
                
                # Format entries
                for entry in sorted(entries):
                    entry_path = os.path.join(file_path, entry)
                    context = MACManager.get_file_context(entry_path)
                    
                    if long_format:
                        # Get file info
                        stat_info = os.stat(entry_path)
                        file_type = "d" if os.path.isdir(entry_path) else "-"
                        mode = stat_info.st_mode
                        perms = ""
                        for perm in ["r", "w", "x"]:
                            perms += perm if mode & 0o400 else "-"
                            mode <<= 1
                        
                        # Format mode, links, owner, group, size, date, name
                        mode_str = f"{file_type}{perms}"
                        links = stat_info.st_nlink
                        owner = UserManager.get_user_by_uid(stat_info.st_uid).username
                        group = GroupManager.get_group_by_gid(stat_info.st_gid).name
                        size = stat_info.st_size
                        
                        output.append(f"{context} {mode_str} {links:<2} {owner:<8} {group:<8} {size:<8} {entry}")
                    else:
                        output.append(f"{context} {entry}")
                
                # Process subdirectories if recursive
                if recursive:
                    for entry in entries:
                        entry_path = os.path.join(file_path, entry)
                        if os.path.isdir(entry_path):
                            # Add recursive listing
                            sub_result = MACUtilities.do_ls_Z(fs, entry_path, "-Z" + ("l" if long_format else "") + ("R" if recursive else ""))
                            output.append(f"\n{entry_path}:")
                            output.append(sub_result)
            else:
                # List single file
                context = MACManager.get_file_context(file_path)
                
                if long_format:
                    # Get file info
                    stat_info = os.stat(file_path)
                    file_type = "d" if os.path.isdir(file_path) else "-"
                    mode = stat_info.st_mode
                    perms = ""
                    for perm in ["r", "w", "x"]:
                        perms += perm if mode & 0o400 else "-"
                        mode <<= 1
                    
                    # Format mode, links, owner, group, size, date, name
                    mode_str = f"{file_type}{perms}"
                    links = stat_info.st_nlink
                    owner = UserManager.get_user_by_uid(stat_info.st_uid).username
                    group = GroupManager.get_group_by_gid(stat_info.st_gid).name
                    size = stat_info.st_size
                    
                    output.append(f"{context} {mode_str} {links:<2} {owner:<8} {group:<8} {size:<8} {os.path.basename(file_path)}")
                else:
                    output.append(f"{context} {os.path.basename(file_path)}")
        
        return "\n".join(output)
    
    @staticmethod
    def do_restorecon(fs, cwd, arg):
        """
        Restore default MAC contexts for files
        
        Usage: restorecon [options] file...
        
        Options:
          -R, --recursive      Operate on files and directories recursively
          -v, --verbose        Show changes in file labels
          -n, --nochange       Don't change any file labels
        """
        args = shlex.split(arg)
        
        if not args:
            return MACUtilities.do_restorecon.__doc__
        
        # Parse options
        recursive = False
        verbose = False
        no_change = False
        files = []
        
        for arg in args:
            if arg in ["-R", "--recursive"]:
                recursive = True
            elif arg in ["-v", "--verbose"]:
                verbose = True
            elif arg in ["-n", "--nochange"]:
                no_change = True
            elif not arg.startswith("-"):
                # Resolve relative path
                path = os.path.join(cwd, arg) if not os.path.isabs(arg) else arg
                files.append(path)
        
        if not files:
            return "restorecon: no files specified"
        
        # Process files
        changes = []
        
        for file_path in files:
            if not os.path.exists(file_path):
                changes.append(f"restorecon: cannot access '{file_path}': No such file or directory")
                continue
            
            # Get file paths to process
            paths_to_process = []
            if recursive and os.path.isdir(file_path):
                for root, dirs, files in os.walk(file_path):
                    paths_to_process.append(root)
                    for name in files:
                        paths_to_process.append(os.path.join(root, name))
            else:
                paths_to_process.append(file_path)
            
            # Process each file
            for path in paths_to_process:
                # Get current context
                current_context = MACManager.get_file_context(path)
                
                # Find matching file context pattern
                patterns = MACManager.list_file_context_patterns()
                matched_pattern = None
                
                for pattern in patterns:
                    if pattern.matches(path):
                        matched_pattern = pattern
                        break
                
                if matched_pattern:
                    # Check if context needs to be changed
                    if current_context != matched_pattern.context:
                        if verbose:
                            changes.append(f"{path}: {current_context} -> {matched_pattern.context}")
                        
                        if not no_change:
                            MACManager.set_file_context(path, matched_pattern.context)
                elif verbose:
                    changes.append(f"{path}: no matching pattern found")
        
        if not changes:
            return "No context changes needed"
        else:
            return "\n".join(changes)
    
    @staticmethod
    def do_setsebool(fs, cwd, arg):
        """
        Set MAC boolean value
        
        Usage: setsebool [options] boolean value
        
        Options:
          -P                   Make change permanent
        """
        return "setsebool: KOS MAC implementation does not support booleans"
    
    @staticmethod
    def do_getsebool(fs, cwd, arg):
        """
        Get MAC boolean value
        
        Usage: getsebool [options] boolean
        
        Options:
          -a                   Show all booleans
        """
        return "getsebool: KOS MAC implementation does not support booleans"
    
    @staticmethod
    def do_load_policy(fs, cwd, arg):
        """
        Load MAC policy
        
        Usage: load_policy [policy_file]
        """
        args = shlex.split(arg)
        
        # Determine policy file
        if args:
            policy_file = args[0]
            # Resolve relative path
            if not os.path.isabs(policy_file):
                policy_file = os.path.join(cwd, policy_file)
        else:
            policy_file = os.path.join(os.path.expanduser('~'), '.kos', 'security', 'mac_policy.json')
        
        # Load policy
        success, message = MACManager.load_policy(policy_file)
        return message
    
    @staticmethod
    def do_save_policy(fs, cwd, arg):
        """
        Save MAC policy
        
        Usage: save_policy [policy_file]
        """
        args = shlex.split(arg)
        
        # Determine policy file
        if args:
            policy_file = args[0]
            # Resolve relative path
            if not os.path.isabs(policy_file):
                policy_file = os.path.join(cwd, policy_file)
        else:
            policy_file = os.path.join(os.path.expanduser('~'), '.kos', 'security', 'mac_policy.json')
        
        # Save policy
        success, message = MACManager.save_policy(policy_file)
        return message
    
    @staticmethod
    def do_add_rule(fs, cwd, arg):
        """
        Add a MAC policy rule
        
        Usage: add_rule [options] source_type target_type:class_name [permissions...]
        
        Options:
          --allow              Add allow rule (default)
          --deny               Add deny rule
        """
        args = shlex.split(arg)
        
        if len(args) < 2:
            return MACUtilities.do_add_rule.__doc__
        
        # Parse options
        rule_type = "allow"
        if "--allow" in args:
            rule_type = "allow"
            args.remove("--allow")
        if "--deny" in args:
            rule_type = "deny"
            args.remove("--deny")
        
        # Parse rule components
        source_type = args[0]
        
        # Parse target_type:class_name
        if ":" not in args[1]:
            return "add_rule: invalid target format, use target_type:class_name"
        
        target_parts = args[1].split(":", 1)
        target_type = target_parts[0]
        class_name = target_parts[1]
        
        # Parse permissions
        permissions = args[2:] if len(args) > 2 else ["*"]
        
        # Create rule
        rule = PolicyRule(
            source_type=source_type,
            target_type=target_type,
            class_name=class_name,
            permissions=permissions,
            rule_type=rule_type
        )
        
        # Add rule
        success, message = MACManager.add_policy_rule(rule)
        
        return message
    
    @staticmethod
    def do_remove_rule(fs, cwd, arg):
        """
        Remove a MAC policy rule
        
        Usage: remove_rule [options] source_type target_type:class_name
        
        Options:
          --allow              Remove allow rule (default)
          --deny               Remove deny rule
        """
        args = shlex.split(arg)
        
        if len(args) < 2:
            return MACUtilities.do_remove_rule.__doc__
        
        # Parse options
        rule_type = "allow"
        if "--allow" in args:
            rule_type = "allow"
            args.remove("--allow")
        if "--deny" in args:
            rule_type = "deny"
            args.remove("--deny")
        
        # Parse rule components
        source_type = args[0]
        
        # Parse target_type:class_name
        if ":" not in args[1]:
            return "remove_rule: invalid target format, use target_type:class_name"
        
        target_parts = args[1].split(":", 1)
        target_type = target_parts[0]
        class_name = target_parts[1]
        
        # Remove rule
        success, message = MACManager.remove_policy_rule(
            source_type=source_type,
            target_type=target_type,
            class_name=class_name,
            rule_type=rule_type
        )
        
        return message
    
    @staticmethod
    def do_list_rules(fs, cwd, arg):
        """
        List MAC policy rules
        
        Usage: list_rules [options]
        
        Options:
          --source=TYPE        Filter by source type
          --target=TYPE        Filter by target type
          --class=CLASS        Filter by object class
          --allow              Show only allow rules
          --deny               Show only deny rules
        """
        args = shlex.split(arg)
        
        # Parse options
        source_filter = None
        target_filter = None
        class_filter = None
        allow_only = False
        deny_only = False
        
        for arg in args:
            if arg.startswith("--source="):
                source_filter = arg[9:]
            elif arg.startswith("--target="):
                target_filter = arg[9:]
            elif arg.startswith("--class="):
                class_filter = arg[8:]
            elif arg == "--allow":
                allow_only = True
            elif arg == "--deny":
                deny_only = True
        
        # Get rules
        rules = MACManager.list_policy_rules()
        
        # Apply filters
        if source_filter:
            rules = [r for r in rules if r.source_type == source_filter]
        
        if target_filter:
            rules = [r for r in rules if r.target_type == target_filter]
        
        if class_filter:
            rules = [r for r in rules if r.class_name == class_filter]
        
        if allow_only:
            rules = [r for r in rules if r.rule_type == "allow"]
        
        if deny_only:
            rules = [r for r in rules if r.rule_type == "deny"]
        
        # Format output
        output = []
        for rule in rules:
            output.append(str(rule))
        
        if not output:
            return "No matching rules found"
        
        return "\n".join(output)
    
    @staticmethod
    def do_add_file_context(fs, cwd, arg):
        """
        Add a file context pattern
        
        Usage: add_file_context [options] pattern context
        
        Options:
          --regex              Treat pattern as a regular expression
        """
        args = shlex.split(arg)
        
        if len(args) < 2:
            return MACUtilities.do_add_file_context.__doc__
        
        # Parse options
        regex = "--regex" in args
        if regex:
            args.remove("--regex")
        
        # Parse pattern and context
        pattern = args[0]
        context_str = args[1]
        
        # Create context
        context = SecurityContext.from_string(context_str)
        
        # Add pattern
        success, message = MACManager.add_file_context_pattern(pattern, context, regex)
        
        return message
    
    @staticmethod
    def do_remove_file_context(fs, cwd, arg):
        """
        Remove a file context pattern
        
        Usage: remove_file_context pattern
        """
        args = shlex.split(arg)
        
        if not args:
            return MACUtilities.do_remove_file_context.__doc__
        
        # Parse pattern
        pattern = args[0]
        
        # Remove pattern
        success, message = MACManager.remove_file_context_pattern(pattern)
        
        return message
    
    @staticmethod
    def do_list_file_contexts(fs, cwd, arg):
        """
        List file context patterns
        
        Usage: list_file_contexts [options]
        
        Options:
          --regex              Show only regex patterns
          --glob               Show only glob patterns
        """
        args = shlex.split(arg)
        
        # Parse options
        regex_only = "--regex" in args
        glob_only = "--glob" in args
        
        # Get patterns
        patterns = MACManager.list_file_context_patterns()
        
        # Apply filters
        if regex_only:
            patterns = [p for p in patterns if p.regex]
        
        if glob_only:
            patterns = [p for p in patterns if not p.regex]
        
        # Format output
        output = []
        for pattern in patterns:
            regex_flag = "(regex)" if pattern.regex else ""
            output.append(f"{pattern.pattern} {pattern.context} {regex_flag}")
        
        if not output:
            return "No file context patterns found"
        
        return "\n".join(output)

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("getenforce", MACUtilities.do_getenforce)
    shell.register_command("setenforce", MACUtilities.do_setenforce)
    shell.register_command("sestatus", MACUtilities.do_sestatus)
    shell.register_command("chcon", MACUtilities.do_chcon)
    shell.register_command("ls_Z", MACUtilities.do_ls_Z)
    shell.register_command("restorecon", MACUtilities.do_restorecon)
    shell.register_command("setsebool", MACUtilities.do_setsebool)
    shell.register_command("getsebool", MACUtilities.do_getsebool)
    shell.register_command("load_policy", MACUtilities.do_load_policy)
    shell.register_command("save_policy", MACUtilities.do_save_policy)
    shell.register_command("add_rule", MACUtilities.do_add_rule)
    shell.register_command("remove_rule", MACUtilities.do_remove_rule)
    shell.register_command("list_rules", MACUtilities.do_list_rules)
    shell.register_command("add_file_context", MACUtilities.do_add_file_context)
    shell.register_command("remove_file_context", MACUtilities.do_remove_file_context)
    shell.register_command("list_file_contexts", MACUtilities.do_list_file_contexts)

"""
Access Control List Utilities for KOS Shell

This module provides commands for manipulating Access Control Lists (ACLs)
in a manner similar to Linux/BSD getfacl and setfacl utilities.
"""

import os
import sys
import logging
import shlex
from typing import Dict, List, Any, Optional

# Import KOS components
from kos.security.acl import ACLManager, ACL, ACLEntry
from kos.security.acl import ACL_USER, ACL_GROUP, ACL_MASK, ACL_OTHER
from kos.security.acl import ACL_TYPE_ACCESS, ACL_TYPE_DEFAULT
from kos.security.users import UserManager, GroupManager

# Set up logging
logger = logging.getLogger('KOS.shell.commands.acl_utils')

class ACLUtilities:
    """ACL commands for KOS shell"""
    
    @staticmethod
    def do_getfacl(fs, cwd, arg):
        """
        Display file access control lists
        
        Usage: getfacl [options] file...
        
        Options:
          -a                   Show all entries
          -d                   Show default entries only
          -R                   Recursive operation
          -t                   Show entries in tabular form
        """
        args = shlex.split(arg)
        
        # Parse options
        show_all = True
        show_default_only = False
        recursive = False
        tabular = False
        files = []
        
        for arg in args:
            if arg == "-a":
                show_all = True
            elif arg == "-d":
                show_default_only = True
                show_all = False
            elif arg == "-R":
                recursive = True
            elif arg == "-t":
                tabular = True
            elif not arg.startswith("-"):
                # Resolve relative path
                path = os.path.join(cwd, arg) if not os.path.isabs(arg) else arg
                files.append(path)
        
        if not files:
            return "getfacl: no files specified"
        
        # Process files
        output = []
        
        for file_path in files:
            if not os.path.exists(file_path):
                output.append(f"getfacl: {file_path}: No such file or directory")
                continue
            
            # Get ACL
            acl = ACLManager.get_acl(file_path)
            if not acl:
                output.append(f"getfacl: {file_path}: Cannot get ACL information")
                continue
            
            # Add file header
            if len(files) > 1:
                output.append(f"# file: {file_path}")
            
            # Filter entries by type
            entries = acl.entries
            if show_default_only:
                entries = [e for e in entries if e.acl_type == ACL_TYPE_DEFAULT]
            elif not show_all:
                entries = [e for e in entries if e.acl_type == ACL_TYPE_ACCESS]
            
            # Format entries
            if tabular:
                # Tabular format
                if entries:
                    output.append("# owner: {} group: {}".format(
                        UserManager.get_user_by_uid(os.stat(file_path).st_uid).username,
                        GroupManager.get_group_by_gid(os.stat(file_path).st_gid).name
                    ))
                    output.append("USER      GROUP     OTHER     MASK      ENTRY")
                    
                    # Find entries for each type
                    user_entry = acl.get_entry(ACL_USER, None) or acl.get_entry(ACL_USER, UserManager.get_user_by_uid(os.stat(file_path).st_uid).username)
                    group_entry = acl.get_entry(ACL_GROUP, None) or acl.get_entry(ACL_GROUP, GroupManager.get_group_by_gid(os.stat(file_path).st_gid).name)
                    other_entry = acl.get_entry(ACL_OTHER)
                    mask_entry = acl.get_entry(ACL_MASK)
                    
                    # Create row
                    row = [
                        user_entry.permissions if user_entry else "---",
                        group_entry.permissions if group_entry else "---",
                        other_entry.permissions if other_entry else "---",
                        mask_entry.permissions if mask_entry else "---"
                    ]
                    
                    output.append("{:<9} {:<9} {:<9} {:<9}".format(*row))
                    
                    # Add named entries
                    for entry in entries:
                        if entry.tag == ACL_USER and entry.qualifier:
                            output.append("user:{}:{}".format(entry.qualifier, entry.permissions))
                        elif entry.tag == ACL_GROUP and entry.qualifier:
                            output.append("group:{}:{}".format(entry.qualifier, entry.permissions))
            else:
                # Standard format
                output.append("# owner: {} group: {}".format(
                    UserManager.get_user_by_uid(os.stat(file_path).st_uid).username,
                    GroupManager.get_group_by_gid(os.stat(file_path).st_gid).name
                ))
                
                for entry in entries:
                    if entry.acl_type == ACL_TYPE_DEFAULT:
                        prefix = "default:"
                    else:
                        prefix = ""
                    
                    if entry.qualifier is not None:
                        output.append(f"{prefix}{entry.tag}:{entry.qualifier}:{entry.permissions}")
                    else:
                        output.append(f"{prefix}{entry.tag}::{entry.permissions}")
            
            output.append("")
            
            # Process subdirectories if recursive
            if recursive and os.path.isdir(file_path):
                for root, dirs, files in os.walk(file_path):
                    for name in dirs + files:
                        child_path = os.path.join(root, name)
                        child_acl = ACLManager.get_acl(child_path)
                        if child_acl:
                            output.append(f"# file: {child_path}")
                            
                            # Filter entries by type
                            child_entries = child_acl.entries
                            if show_default_only:
                                child_entries = [e for e in child_entries if e.acl_type == ACL_TYPE_DEFAULT]
                            elif not show_all:
                                child_entries = [e for e in child_entries if e.acl_type == ACL_TYPE_ACCESS]
                            
                            for entry in child_entries:
                                if entry.acl_type == ACL_TYPE_DEFAULT:
                                    prefix = "default:"
                                else:
                                    prefix = ""
                                
                                if entry.qualifier is not None:
                                    output.append(f"{prefix}{entry.tag}:{entry.qualifier}:{entry.permissions}")
                                else:
                                    output.append(f"{prefix}{entry.tag}::{entry.permissions}")
                            
                            output.append("")
        
        return "\n".join(output)
    
    @staticmethod
    def do_setfacl(fs, cwd, arg):
        """
        Set file access control lists
        
        Usage: setfacl [options] acl_spec file...
        
        Options:
          -m, --modify=acl     Modify ACL entries
          -x, --remove=acl     Remove ACL entries
          -b, --remove-all     Remove all ACL entries
          -k, --remove-default Remove default ACL
          -R, --recursive      Recursive operation
          --set=acl            Set ACL, replacing current ACL
          -d, --default        Operations apply to default ACL
        
        ACL specification format:
          u[ser]:name:perm     Set user ACL entry
          g[roup]:name:perm    Set group ACL entry
          m[ask]::perm         Set mask entry
          o[ther]::perm        Set other entry
        """
        args = shlex.split(arg)
        
        if not args:
            return ACLUtilities.do_setfacl.__doc__
        
        # Parse options
        modify_entries = []
        remove_entries = []
        remove_all = False
        remove_default = False
        recursive = False
        set_entries = []
        default_only = False
        files = []
        
        i = 0
        while i < len(args):
            if args[i] in ["-m", "--modify"] and i + 1 < len(args):
                modify_entries.append(args[i + 1])
                i += 2
            elif args[i].startswith("--modify="):
                modify_entries.append(args[i][9:])
                i += 1
            elif args[i] in ["-x", "--remove"] and i + 1 < len(args):
                remove_entries.append(args[i + 1])
                i += 2
            elif args[i].startswith("--remove="):
                remove_entries.append(args[i][9:])
                i += 1
            elif args[i] in ["-b", "--remove-all"]:
                remove_all = True
                i += 1
            elif args[i] in ["-k", "--remove-default"]:
                remove_default = True
                i += 1
            elif args[i] in ["-R", "--recursive"]:
                recursive = True
                i += 1
            elif args[i].startswith("--set="):
                set_entries.append(args[i][6:])
                i += 1
            elif args[i] in ["-d", "--default"]:
                default_only = True
                i += 1
            else:
                # Assume it's a file path
                path = os.path.join(cwd, args[i]) if not os.path.isabs(args[i]) else args[i]
                files.append(path)
                i += 1
        
        if not files:
            return "setfacl: no files specified"
        
        if not (modify_entries or remove_entries or remove_all or remove_default or set_entries):
            return "setfacl: no ACL entries specified"
        
        # Process files
        results = []
        
        for file_path in files:
            if not os.path.exists(file_path):
                results.append(f"setfacl: {file_path}: No such file or directory")
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
                # Get ACL
                acl = ACLManager.get_acl(path)
                if not acl:
                    results.append(f"setfacl: {path}: Cannot get ACL information")
                    continue
                
                modified = False
                
                # Handle remove all
                if remove_all:
                    acl.entries = [e for e in acl.entries if e.tag in [ACL_USER, ACL_GROUP, ACL_OTHER] and e.qualifier is None]
                    modified = True
                
                # Handle remove default
                if remove_default:
                    acl.entries = [e for e in acl.entries if e.acl_type != ACL_TYPE_DEFAULT]
                    modified = True
                
                # Handle set (replace all)
                if set_entries:
                    # Clear existing entries except base ones if not removing all
                    if not remove_all:
                        acl.entries = [e for e in acl.entries if e.tag in [ACL_USER, ACL_GROUP, ACL_OTHER] and e.qualifier is None]
                    
                    # Parse and add new entries
                    for entry_spec in set_entries:
                        success, message, entry = ACLUtilities._parse_acl_entry(entry_spec, default_only)
                        if not success:
                            results.append(f"setfacl: {message}")
                            continue
                        
                        acl.add_entry(entry)
                        modified = True
                
                # Handle modify
                for entry_spec in modify_entries:
                    success, message, entry = ACLUtilities._parse_acl_entry(entry_spec, default_only)
                    if not success:
                        results.append(f"setfacl: {message}")
                        continue
                    
                    acl.add_entry(entry)
                    modified = True
                
                # Handle remove
                for entry_spec in remove_entries:
                    success, message, entry = ACLUtilities._parse_acl_entry(entry_spec, default_only, True)
                    if not success:
                        results.append(f"setfacl: {message}")
                        continue
                    
                    acl.remove_entry(entry.tag, entry.qualifier, entry.acl_type)
                    modified = True
                
                # Save ACL if modified
                if modified:
                    success, message = ACLManager.set_acl(path, acl)
                    if not success:
                        results.append(f"setfacl: {path}: {message}")
        
        if not results:
            return "ACLs modified successfully"
        else:
            return "\n".join(results)
    
    @staticmethod
    def _parse_acl_entry(entry_spec: str, default_only: bool = False, remove_mode: bool = False) -> Tuple[bool, str, Optional[ACLEntry]]:
        """
        Parse an ACL entry specification
        
        Args:
            entry_spec: ACL entry specification string
            default_only: Whether entry is for default ACL
            remove_mode: If True, permissions are ignored
        
        Returns:
            (success, message, entry)
        """
        parts = entry_spec.split(':')
        
        if len(parts) < 2 or (not remove_mode and len(parts) < 3):
            return False, f"Invalid ACL entry specification: {entry_spec}", None
        
        # Handle default prefix
        acl_type = ACL_TYPE_DEFAULT if default_only else ACL_TYPE_ACCESS
        tag = parts[0]
        
        if tag.startswith("d:") or tag.startswith("default:"):
            acl_type = ACL_TYPE_DEFAULT
            tag = tag.split(":", 1)[1]
        
        # Parse tag
        if tag in ["u", "user"]:
            tag = ACL_USER
        elif tag in ["g", "group"]:
            tag = ACL_GROUP
        elif tag in ["m", "mask"]:
            tag = ACL_MASK
        elif tag in ["o", "other"]:
            tag = ACL_OTHER
        else:
            return False, f"Invalid ACL tag: {tag}", None
        
        # Parse qualifier
        qualifier = parts[1] if parts[1] else None
        
        if qualifier is not None:
            # Verify user/group exists
            if tag == ACL_USER and not UserManager.get_user_by_name(qualifier):
                return False, f"User not found: {qualifier}", None
            elif tag == ACL_GROUP and not GroupManager.get_group_by_name(qualifier):
                return False, f"Group not found: {qualifier}", None
        
        # Parse permissions
        permissions = "rwx" if remove_mode else parts[2]
        
        # Create entry
        entry = ACLEntry(tag, qualifier, permissions, acl_type)
        
        return True, "Entry parsed successfully", entry
    
    @staticmethod
    def do_chacl(fs, cwd, arg):
        """
        Change ACL of a file
        
        Usage: chacl [-R] acl_entries pathname...
        
        Options:
          -R                   Recursive operation
        
        ACL entries format:
          u:user:perms[,g:group:perms]...
        """
        args = shlex.split(arg)
        
        if len(args) < 2:
            return ACLUtilities.do_chacl.__doc__
        
        # Parse options
        recursive = False
        acl_entries = None
        files = []
        
        i = 0
        while i < len(args):
            if args[i] == "-R":
                recursive = True
                i += 1
            elif acl_entries is None:
                acl_entries = args[i]
                i += 1
            else:
                # Assume it's a file path
                path = os.path.join(cwd, args[i]) if not os.path.isabs(args[i]) else args[i]
                files.append(path)
                i += 1
        
        if not files:
            return "chacl: no files specified"
        
        if not acl_entries:
            return "chacl: no ACL entries specified"
        
        # Parse ACL entries
        entries = []
        for entry_spec in acl_entries.split(','):
            success, message, entry = ACLUtilities._parse_acl_entry(entry_spec)
            if not success:
                return f"chacl: {message}"
            entries.append(entry)
        
        # Process files
        results = []
        
        for file_path in files:
            if not os.path.exists(file_path):
                results.append(f"chacl: {file_path}: No such file or directory")
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
                # Get ACL
                acl = ACLManager.get_acl(path)
                if not acl:
                    results.append(f"chacl: {path}: Cannot get ACL information")
                    continue
                
                # Apply entries
                for entry in entries:
                    acl.add_entry(entry)
                
                # Save ACL
                success, message = ACLManager.set_acl(path, acl)
                if not success:
                    results.append(f"chacl: {path}: {message}")
        
        if not results:
            return "ACLs changed successfully"
        else:
            return "\n".join(results)

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("getfacl", ACLUtilities.do_getfacl)
    shell.register_command("setfacl", ACLUtilities.do_setfacl)
    shell.register_command("chacl", ACLUtilities.do_chacl)

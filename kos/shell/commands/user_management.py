"""
User Management Utilities for KOS Shell

This module provides commands to manage users and groups in KOS.
"""

import os
import sys
import time
import logging
import json
import shlex
import getpass
from typing import Dict, List, Any, Optional, Union

# Import KOS components
from kos.security.users import UserManager, GroupManager

# Set up logging
logger = logging.getLogger('KOS.shell.commands.user_management')

class UserUtilities:
    """User management commands for KOS shell"""
    
    @staticmethod
    def do_useradd(fs, cwd, arg):
        """
        Create a new user
        
        Usage: useradd [options] USERNAME
        
        Options:
          -c, --comment COMMENT      Full name
          -d, --home-dir HOME_DIR    Home directory
          -g, --gid GID              Primary group ID
          -G, --groups GROUPS        Supplementary groups (comma-separated)
          -m, --create-home          Create home directory
          -s, --shell SHELL          Login shell
          -u, --uid UID              User ID
          -r, --system               Create system user
        """
        args = shlex.split(arg)
        
        if not args:
            return UserUtilities.do_useradd.__doc__
        
        # Parse options
        username = None
        uid = None
        gid = None
        full_name = ""
        home_dir = None
        shell = None
        groups = None
        create_home = False
        system_user = False
        
        i = 0
        while i < len(args):
            if args[i] in ["-c", "--comment"]:
                if i + 1 < len(args):
                    full_name = args[i+1]
                    i += 2
                else:
                    return "useradd: option requires an argument -- '-c'"
            elif args[i] in ["-d", "--home-dir"]:
                if i + 1 < len(args):
                    home_dir = args[i+1]
                    i += 2
                else:
                    return "useradd: option requires an argument -- '-d'"
            elif args[i] in ["-g", "--gid"]:
                if i + 1 < len(args):
                    try:
                        gid = int(args[i+1])
                    except ValueError:
                        # Try to resolve group name
                        group = GroupManager.get_group_by_name(args[i+1])
                        if not group:
                            return f"useradd: group '{args[i+1]}' does not exist"
                        gid = group.gid
                    i += 2
                else:
                    return "useradd: option requires an argument -- '-g'"
            elif args[i] in ["-G", "--groups"]:
                if i + 1 < len(args):
                    groups = args[i+1].split(",")
                    # Validate groups
                    for group_name in groups:
                        if not GroupManager.get_group_by_name(group_name):
                            return f"useradd: group '{group_name}' does not exist"
                    i += 2
                else:
                    return "useradd: option requires an argument -- '-G'"
            elif args[i] in ["-m", "--create-home"]:
                create_home = True
                i += 1
            elif args[i] in ["-s", "--shell"]:
                if i + 1 < len(args):
                    shell = args[i+1]
                    i += 2
                else:
                    return "useradd: option requires an argument -- '-s'"
            elif args[i] in ["-u", "--uid"]:
                if i + 1 < len(args):
                    try:
                        uid = int(args[i+1])
                    except ValueError:
                        return f"useradd: invalid user ID '{args[i+1]}'"
                    i += 2
                else:
                    return "useradd: option requires an argument -- '-u'"
            elif args[i] in ["-r", "--system"]:
                system_user = True
                i += 1
            else:
                if username is None:
                    username = args[i]
                i += 1
        
        if username is None:
            return "useradd: username is required"
        
        # Create user
        success, message, user = UserManager.create_user(
            username=username,
            uid=uid,
            gid=gid,
            full_name=full_name,
            home_dir=home_dir,
            shell=shell,
            groups=groups,
            system_user=system_user
        )
        
        if not success:
            return f"useradd: {message}"
        
        # Create home directory if requested
        if create_home and user.home_dir:
            try:
                os.makedirs(user.home_dir, exist_ok=True)
            except Exception as e:
                return f"useradd: failed to create home directory: {str(e)}"
        
        # Save changes
        security_dir = os.path.join(os.path.expanduser('~'), '.kos', 'security')
        users_db = os.path.join(security_dir, 'users.json')
        groups_db = os.path.join(security_dir, 'groups.json')
        UserManager.save_users(users_db)
        GroupManager.save_groups(groups_db)
        
        return f"User '{username}' added"
    
    @staticmethod
    def do_userdel(fs, cwd, arg):
        """
        Delete a user
        
        Usage: userdel [options] USERNAME
        
        Options:
          -r, --remove-home          Remove home directory
        """
        args = shlex.split(arg)
        
        if not args:
            return UserUtilities.do_userdel.__doc__
        
        # Parse options
        username = None
        remove_home = False
        
        i = 0
        while i < len(args):
            if args[i] in ["-r", "--remove-home"]:
                remove_home = True
                i += 1
            else:
                if username is None:
                    username = args[i]
                i += 1
        
        if username is None:
            return "userdel: username is required"
        
        # Delete user
        success, message = UserManager.delete_user(username, remove_home)
        
        if not success:
            return f"userdel: {message}"
        
        # Save changes
        security_dir = os.path.join(os.path.expanduser('~'), '.kos', 'security')
        users_db = os.path.join(security_dir, 'users.json')
        groups_db = os.path.join(security_dir, 'groups.json')
        UserManager.save_users(users_db)
        GroupManager.save_groups(groups_db)
        
        return message
    
    @staticmethod
    def do_usermod(fs, cwd, arg):
        """
        Modify a user
        
        Usage: usermod [options] USERNAME
        
        Options:
          -c, --comment COMMENT      Full name
          -d, --home-dir HOME_DIR    Home directory
          -g, --gid GID              Primary group ID
          -G, --groups GROUPS        Supplementary groups (comma-separated)
          -l, --login NEW_LOGIN      New username
          -s, --shell SHELL          Login shell
          -u, --uid UID              User ID
          -L, --lock                 Lock user account
          -U, --unlock               Unlock user account
        """
        args = shlex.split(arg)
        
        if not args:
            return UserUtilities.do_usermod.__doc__
        
        # Parse options
        username = None
        uid = None
        gid = None
        full_name = None
        home_dir = None
        shell = None
        groups = None
        new_login = None
        lock = None
        
        i = 0
        while i < len(args):
            if args[i] in ["-c", "--comment"]:
                if i + 1 < len(args):
                    full_name = args[i+1]
                    i += 2
                else:
                    return "usermod: option requires an argument -- '-c'"
            elif args[i] in ["-d", "--home-dir"]:
                if i + 1 < len(args):
                    home_dir = args[i+1]
                    i += 2
                else:
                    return "usermod: option requires an argument -- '-d'"
            elif args[i] in ["-g", "--gid"]:
                if i + 1 < len(args):
                    try:
                        gid = int(args[i+1])
                    except ValueError:
                        # Try to resolve group name
                        group = GroupManager.get_group_by_name(args[i+1])
                        if not group:
                            return f"usermod: group '{args[i+1]}' does not exist"
                        gid = group.gid
                    i += 2
                else:
                    return "usermod: option requires an argument -- '-g'"
            elif args[i] in ["-G", "--groups"]:
                if i + 1 < len(args):
                    groups = args[i+1].split(",")
                    # Validate groups
                    for group_name in groups:
                        if not GroupManager.get_group_by_name(group_name):
                            return f"usermod: group '{group_name}' does not exist"
                    i += 2
                else:
                    return "usermod: option requires an argument -- '-G'"
            elif args[i] in ["-l", "--login"]:
                if i + 1 < len(args):
                    new_login = args[i+1]
                    i += 2
                else:
                    return "usermod: option requires an argument -- '-l'"
            elif args[i] in ["-s", "--shell"]:
                if i + 1 < len(args):
                    shell = args[i+1]
                    i += 2
                else:
                    return "usermod: option requires an argument -- '-s'"
            elif args[i] in ["-u", "--uid"]:
                if i + 1 < len(args):
                    try:
                        uid = int(args[i+1])
                    except ValueError:
                        return f"usermod: invalid user ID '{args[i+1]}'"
                    i += 2
                else:
                    return "usermod: option requires an argument -- '-u'"
            elif args[i] in ["-L", "--lock"]:
                lock = True
                i += 1
            elif args[i] in ["-U", "--unlock"]:
                lock = False
                i += 1
            else:
                if username is None:
                    username = args[i]
                i += 1
        
        if username is None:
            return "usermod: username is required"
        
        # Find user
        user = UserManager.get_user_by_name(username)
        if not user:
            return f"usermod: user '{username}' does not exist"
        
        # Lock/unlock if requested
        if lock is not None:
            if lock:
                user.lock()
            else:
                user.unlock()
        
        # Modify user
        if new_login is not None:
            # This requires special handling as we need to change the username
            # In a real implementation, this would be more complex
            user.username = new_login
            username = new_login
        
        success, message = UserManager.modify_user(
            username=username,
            uid=uid,
            gid=gid,
            full_name=full_name,
            home_dir=home_dir,
            shell=shell,
            groups=groups
        )
        
        if not success:
            return f"usermod: {message}"
        
        # Save changes
        security_dir = os.path.join(os.path.expanduser('~'), '.kos', 'security')
        users_db = os.path.join(security_dir, 'users.json')
        groups_db = os.path.join(security_dir, 'groups.json')
        UserManager.save_users(users_db)
        GroupManager.save_groups(groups_db)
        
        return f"User '{username}' modified"
    
    @staticmethod
    def do_passwd(fs, cwd, arg):
        """
        Change password for a user
        
        Usage: passwd [username]
        """
        args = shlex.split(arg)
        
        # Determine username
        username = None
        if args:
            username = args[0]
        else:
            # Default to current user
            username = "root"  # In a real implementation, this would be the current user
        
        # Find user
        user = UserManager.get_user_by_name(username)
        if not user:
            return f"passwd: user '{username}' does not exist"
        
        # Get new password
        # In a real implementation, this would be hidden input
        password = "password"  # Simulated password
        
        # Set password
        user.set_password(password)
        
        # Save changes
        security_dir = os.path.join(os.path.expanduser('~'), '.kos', 'security')
        users_db = os.path.join(security_dir, 'users.json')
        UserManager.save_users(users_db)
        
        return f"Password changed for user '{username}'"
    
    @staticmethod
    def do_id(fs, cwd, arg):
        """
        Print user and group information
        
        Usage: id [username]
        """
        args = shlex.split(arg)
        
        # Determine username
        username = None
        if args:
            username = args[0]
        else:
            # Default to current user
            username = "root"  # In a real implementation, this would be the current user
        
        # Find user
        user = UserManager.get_user_by_name(username)
        if not user:
            return f"id: '{username}': no such user"
        
        # Get primary group
        primary_group = GroupManager.get_group_by_gid(user.gid)
        if not primary_group:
            primary_group_name = f"gid={user.gid}"
        else:
            primary_group_name = primary_group.name
        
        # Build groups string
        groups_str = f"{user.gid}({primary_group_name})"
        
        if user.groups:
            for group_name in user.groups:
                group = GroupManager.get_group_by_name(group_name)
                if group:
                    groups_str += f",{group.gid}({group_name})"
        
        return f"uid={user.uid}({user.username}) gid={user.gid}({primary_group_name}) groups={groups_str}"
    
    @staticmethod
    def do_groupadd(fs, cwd, arg):
        """
        Create a new group
        
        Usage: groupadd [options] GROUP
        
        Options:
          -g, --gid GID              Group ID
          -r, --system               Create system group
        """
        args = shlex.split(arg)
        
        if not args:
            return UserUtilities.do_groupadd.__doc__
        
        # Parse options
        group_name = None
        gid = None
        system_group = False
        
        i = 0
        while i < len(args):
            if args[i] in ["-g", "--gid"]:
                if i + 1 < len(args):
                    try:
                        gid = int(args[i+1])
                    except ValueError:
                        return f"groupadd: invalid group ID '{args[i+1]}'"
                    i += 2
                else:
                    return "groupadd: option requires an argument -- '-g'"
            elif args[i] in ["-r", "--system"]:
                system_group = True
                i += 1
            else:
                if group_name is None:
                    group_name = args[i]
                i += 1
        
        if group_name is None:
            return "groupadd: group name is required"
        
        # Create group
        success, message, group = GroupManager.create_group(
            name=group_name,
            gid=gid,
            system_group=system_group
        )
        
        if not success:
            return f"groupadd: {message}"
        
        # Save changes
        security_dir = os.path.join(os.path.expanduser('~'), '.kos', 'security')
        groups_db = os.path.join(security_dir, 'groups.json')
        GroupManager.save_groups(groups_db)
        
        return f"Group '{group_name}' added"
    
    @staticmethod
    def do_groupdel(fs, cwd, arg):
        """
        Delete a group
        
        Usage: groupdel GROUP
        """
        args = shlex.split(arg)
        
        if not args:
            return UserUtilities.do_groupdel.__doc__
        
        group_name = args[0]
        
        # Delete group
        success, message = GroupManager.delete_group(group_name)
        
        if not success:
            return f"groupdel: {message}"
        
        # Save changes
        security_dir = os.path.join(os.path.expanduser('~'), '.kos', 'security')
        groups_db = os.path.join(security_dir, 'groups.json')
        GroupManager.save_groups(groups_db)
        
        return message
    
    @staticmethod
    def do_groupmod(fs, cwd, arg):
        """
        Modify a group
        
        Usage: groupmod [options] GROUP
        
        Options:
          -g, --gid GID              Group ID
          -n, --new-name NEW_NAME    New group name
        """
        args = shlex.split(arg)
        
        if not args:
            return UserUtilities.do_groupmod.__doc__
        
        # Parse options
        group_name = None
        gid = None
        new_name = None
        
        i = 0
        while i < len(args):
            if args[i] in ["-g", "--gid"]:
                if i + 1 < len(args):
                    try:
                        gid = int(args[i+1])
                    except ValueError:
                        return f"groupmod: invalid group ID '{args[i+1]}'"
                    i += 2
                else:
                    return "groupmod: option requires an argument -- '-g'"
            elif args[i] in ["-n", "--new-name"]:
                if i + 1 < len(args):
                    new_name = args[i+1]
                    i += 2
                else:
                    return "groupmod: option requires an argument -- '-n'"
            else:
                if group_name is None:
                    group_name = args[i]
                i += 1
        
        if group_name is None:
            return "groupmod: group name is required"
        
        # Modify group
        success, message = GroupManager.modify_group(
            name=group_name,
            new_name=new_name,
            gid=gid
        )
        
        if not success:
            return f"groupmod: {message}"
        
        # Save changes
        security_dir = os.path.join(os.path.expanduser('~'), '.kos', 'security')
        users_db = os.path.join(security_dir, 'users.json')
        groups_db = os.path.join(security_dir, 'groups.json')
        UserManager.save_users(users_db)
        GroupManager.save_groups(groups_db)
        
        return f"Group '{group_name}' modified"
    
    @staticmethod
    def do_groups(fs, cwd, arg):
        """
        Print group memberships
        
        Usage: groups [username]
        """
        args = shlex.split(arg)
        
        # Determine username
        username = None
        if args:
            username = args[0]
        else:
            # Default to current user
            username = "root"  # In a real implementation, this would be the current user
        
        # Find user
        user = UserManager.get_user_by_name(username)
        if not user:
            return f"groups: '{username}': no such user"
        
        # Get primary group
        primary_group = GroupManager.get_group_by_gid(user.gid)
        if not primary_group:
            primary_group_name = f"gid={user.gid}"
        else:
            primary_group_name = primary_group.name
        
        # Build groups list
        groups_list = [primary_group_name]
        
        if user.groups:
            for group_name in user.groups:
                if group_name != primary_group_name:
                    groups_list.append(group_name)
        
        return f"{username} : {' '.join(groups_list)}"
    
    @staticmethod
    def do_who(fs, cwd, arg):
        """
        Print information about users who are currently logged in
        
        Usage: who [options]
        
        Options:
          -b, --boot                 Print system boot time
          -r, --runlevel             Print current runlevel
          -u, --users                Print only logged-in users
          -H, --heading              Print column headings
        """
        # This is a simplified implementation
        return "root     pts/0        May 25 03:44"
    
    @staticmethod
    def do_whoami(fs, cwd, arg):
        """
        Print current user name
        
        Usage: whoami
        """
        # This is a simplified implementation
        return "root"
    
    @staticmethod
    def do_last(fs, cwd, arg):
        """
        Print listing of last logged in users
        
        Usage: last [options] [username]
        """
        # This is a simplified implementation
        return "root     pts/0        localhost      Sat May 25 03:44   still logged in"

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("useradd", UserUtilities.do_useradd)
    shell.register_command("userdel", UserUtilities.do_userdel)
    shell.register_command("usermod", UserUtilities.do_usermod)
    shell.register_command("passwd", UserUtilities.do_passwd)
    shell.register_command("id", UserUtilities.do_id)
    shell.register_command("groupadd", UserUtilities.do_groupadd)
    shell.register_command("groupdel", UserUtilities.do_groupdel)
    shell.register_command("groupmod", UserUtilities.do_groupmod)
    shell.register_command("groups", UserUtilities.do_groups)
    shell.register_command("who", UserUtilities.do_who)
    shell.register_command("whoami", UserUtilities.do_whoami)
    shell.register_command("last", UserUtilities.do_last)

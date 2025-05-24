"""
Authentication Utilities for KOS Shell

This module provides commands for authentication and session management in KOS.
"""

import os
import sys
import time
import logging
import shlex
import getpass
from typing import Dict, List, Any, Optional, Union

# Import KOS components
from kos.security.users import UserManager
from kos.security.auth import login, logout, switch_user, get_current_user, list_sessions

# Set up logging
logger = logging.getLogger('KOS.shell.commands.auth_utils')

class AuthUtilities:
    """Authentication commands for KOS shell"""
    
    @staticmethod
    def do_login(fs, cwd, arg):
        """
        Log in as a user
        
        Usage: login [username]
        """
        args = shlex.split(arg)
        
        # Get username
        username = None
        if args:
            username = args[0]
        else:
            username = input("Username: ")
        
        # Get password
        password = getpass.getpass("Password: ")
        
        # Attempt login
        success, message, session = login(username, password)
        
        if not success:
            return f"Login failed: {message}"
        
        return f"Login successful. Welcome, {username}!"
    
    @staticmethod
    def do_logout(fs, cwd, arg):
        """
        Log out of current session
        
        Usage: logout
        """
        # This is a simplified implementation
        # In a real system, this would use the session ID
        return "Logged out"
    
    @staticmethod
    def do_su(fs, cwd, arg):
        """
        Switch user
        
        Usage: su [options] [username]
        
        Options:
          -l, --login          Make the shell a login shell
          -c, --command CMD    Command to execute
        """
        args = shlex.split(arg)
        
        # Parse options
        username = None
        login_shell = False
        command = None
        
        i = 0
        while i < len(args):
            if args[i] in ["-l", "--login"]:
                login_shell = True
                i += 1
            elif args[i] in ["-c", "--command"]:
                if i + 1 < len(args):
                    command = args[i+1]
                    i += 2
                else:
                    return "su: option requires an argument -- '-c'"
            else:
                if username is None:
                    username = args[i]
                i += 1
        
        # Default to root if no username specified
        if username is None:
            username = "root"
        
        # If switching to a non-root user, need to ask for password
        current_user = get_current_user()
        password = None
        
        if current_user.uid != 0 and username != "root":
            password = getpass.getpass("Password: ")
        
        # Switch user
        success, message = switch_user(username, password)
        
        if not success:
            return f"su: {message}"
        
        # Execute command if specified
        if command:
            # In a real implementation, this would execute the command as the new user
            return f"Executing '{command}' as {username}"
        
        return message
    
    @staticmethod
    def do_sudo(fs, cwd, arg):
        """
        Execute command as another user
        
        Usage: sudo [options] command
        
        Options:
          -u, --user USER      User to execute as (default: root)
          -l, --list           List allowed commands
          -i, --login          Run login shell
        """
        args = shlex.split(arg)
        
        if not args:
            return AuthUtilities.do_sudo.__doc__
        
        # Parse options
        username = "root"  # Default to root
        login_shell = False
        list_commands = False
        command_args = []
        
        i = 0
        while i < len(args):
            if args[i] in ["-u", "--user"]:
                if i + 1 < len(args):
                    username = args[i+1]
                    i += 2
                else:
                    return "sudo: option requires an argument -- '-u'"
            elif args[i] in ["-l", "--list"]:
                list_commands = True
                i += 1
            elif args[i] in ["-i", "--login"]:
                login_shell = True
                i += 1
            else:
                command_args = args[i:]
                break
        
        # Handle list command
        if list_commands:
            # In a real implementation, this would show the sudoers file entries for the current user
            return "User root may run the following commands on this host:\n    (ALL : ALL) ALL"
        
        # If no command specified
        if not command_args:
            return "sudo: no command specified"
        
        # Get current user
        current_user = get_current_user()
        
        # Check if user is in sudo group (wheel)
        if current_user.uid != 0 and "wheel" not in current_user.groups:
            return "sudo: user not in sudoers file"
        
        # Ask for password if not root
        if current_user.uid != 0:
            password = getpass.getpass("[sudo] password for {}: ".format(current_user.username))
            
            # Verify password
            if not current_user.check_password(password):
                return "sudo: incorrect password"
        
        # Execute command as specified user
        command = ' '.join(command_args)
        
        # In a real implementation, this would execute the command as the specified user
        return f"Executing '{command}' as {username}"
    
    @staticmethod
    def do_w(fs, cwd, arg):
        """
        Show who is logged in and what they are doing
        
        Usage: w [options] [user]
        
        Options:
          -h, --no-header      Do not print header
          -s, --short          Short format
        """
        args = shlex.split(arg)
        
        # Parse options
        show_header = True
        short_format = False
        filter_user = None
        
        i = 0
        while i < len(args):
            if args[i] in ["-h", "--no-header"]:
                show_header = False
                i += 1
            elif args[i] in ["-s", "--short"]:
                short_format = True
                i += 1
            else:
                if filter_user is None:
                    filter_user = args[i]
                i += 1
        
        # Get sessions
        sessions = list_sessions()
        
        # Filter by user if specified
        if filter_user:
            sessions = [s for s in sessions if s.user.username == filter_user]
        
        # Build output
        output = []
        
        if show_header:
            current_time = time.strftime("%H:%M:%S", time.localtime())
            uptime = "1 day"  # Simulated uptime
            users_count = len(sessions)
            
            output.append(f" {current_time} up {uptime}, {users_count} user{'s' if users_count != 1 else ''}")
            
            if not short_format:
                output.append("USER     TTY      FROM             LOGIN@   IDLE   WHAT")
            else:
                output.append("USER     TTY      IDLE  WHAT")
        
        # Add session info
        for session in sessions:
            username = session.user.username
            tty = session.terminal
            remote = session.remote_host
            login_time = time.strftime("%H:%M", time.localtime(session.start_time))
            idle_time = int(time.time() - session.last_activity)
            idle_str = f"{idle_time//60}:{idle_time%60:02d}" if idle_time > 0 else "0:00"
            what = "kosh"  # Simulated command
            
            if not short_format:
                output.append(f"{username:<8} {tty:<8} {remote:<16} {login_time:<8} {idle_str:<6} {what}")
            else:
                output.append(f"{username:<8} {tty:<8} {idle_str:<5} {what}")
        
        return "\n".join(output)

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("login", AuthUtilities.do_login)
    shell.register_command("logout", AuthUtilities.do_logout)
    shell.register_command("su", AuthUtilities.do_su)
    shell.register_command("sudo", AuthUtilities.do_sudo)
    shell.register_command("w", AuthUtilities.do_w)

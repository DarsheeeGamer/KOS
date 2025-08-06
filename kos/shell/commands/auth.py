"""
Authentication and user management commands for KOS Shell
"""

import types
import getpass
from typing import Optional

def register_commands(shell):
    """Register authentication commands with shell"""
    
    def do_login(self, arg):
        """Login as a user
        Usage: login [username]"""
        if not self.auth:
            print("Authentication system not available")
            return
        
        # Get username
        username = arg.strip() if arg else input("Username: ")
        if not username:
            return
        
        # Get password (hidden input)
        try:
            password = getpass.getpass("Password: ")
        except KeyboardInterrupt:
            print("\nLogin cancelled")
            return
        
        # Attempt login
        if self.auth.authenticate(username, password):
            print(f"Logged in as {username}")
            # Update prompt
            self.prompt = f"{username}@kos:{self.cwd}> "
            # Change to user's home directory
            user = self.auth.get_current_user()
            if user and self.vfs.exists(user.home_dir):
                self.cwd = user.home_dir
        else:
            print("Login failed: Invalid username or password")
    
    def do_logout(self, arg):
        """Logout current user"""
        if not self.auth:
            print("Authentication system not available")
            return
        
        self.auth.logout()
        print("Logged out")
        self.prompt = "kos> "
        self.cwd = "/"
    
    def do_whoami(self, arg):
        """Display current username"""
        if not self.auth:
            print("Authentication system not available")
            return
        
        user = self.auth.get_current_user()
        if user:
            print(user.username)
        else:
            print("Not logged in")
    
    def do_passwd(self, arg):
        """Change user password
        Usage: passwd [username]"""
        if not self.auth:
            print("Authentication system not available")
            return
        
        current_user = self.auth.get_current_user()
        if not current_user:
            print("Not logged in")
            return
        
        # Determine target user
        target_username = arg.strip() if arg else current_user.username
        
        # Check permissions
        if target_username != current_user.username and current_user.role.value != "root":
            print("passwd: You may not change the password for other users")
            return
        
        try:
            # Get old password (unless root changing another user's password)
            old_password = ""
            if current_user.role.value != "root" or target_username == current_user.username:
                old_password = getpass.getpass("Current password: ")
            
            # Get new password
            new_password = getpass.getpass("New password: ")
            confirm_password = getpass.getpass("Confirm new password: ")
            
            if new_password != confirm_password:
                print("Passwords do not match")
                return
            
            if len(new_password) < 4:
                print("Password too short (minimum 4 characters)")
                return
            
            # Change password
            if self.auth.change_password(target_username, old_password, new_password):
                print("Password changed successfully")
            else:
                print("Failed to change password")
                
        except KeyboardInterrupt:
            print("\nPassword change cancelled")
    
    def do_useradd(self, arg):
        """Add a new user
        Usage: useradd <username> [-r role] [-h home_dir] [-g groups]"""
        if not self.auth:
            print("Authentication system not available")
            return
        
        current_user = self.auth.get_current_user()
        if not current_user or current_user.role.value not in ["root", "admin"]:
            print("useradd: Permission denied")
            return
        
        args = arg.split()
        if not args:
            print("Usage: useradd <username> [-r role] [-h home_dir] [-g groups]")
            return
        
        username = args[0]
        role = "user"
        home_dir = None
        groups = ["users"]
        
        # Parse options
        i = 1
        while i < len(args):
            if args[i] == "-r" and i + 1 < len(args):
                role = args[i + 1]
                i += 2
            elif args[i] == "-h" and i + 1 < len(args):
                home_dir = args[i + 1]
                i += 2
            elif args[i] == "-g" and i + 1 < len(args):
                groups = args[i + 1].split(",")
                i += 2
            else:
                i += 1
        
        try:
            # Get password for new user
            password = getpass.getpass(f"Password for {username}: ")
            confirm = getpass.getpass("Confirm password: ")
            
            if password != confirm:
                print("Passwords do not match")
                return
            
            # Create user
            from kos.core.auth import UserRole
            role_enum = UserRole(role) if role in ["root", "admin", "user", "guest"] else UserRole.USER
            
            user = self.auth.create_user(
                username=username,
                password=password,
                role=role_enum,
                home_dir=home_dir,
                groups=groups
            )
            
            if user:
                print(f"User {username} created successfully")
            else:
                print(f"Failed to create user {username}")
                
        except KeyboardInterrupt:
            print("\nUser creation cancelled")
        except Exception as e:
            print(f"Error creating user: {e}")
    
    def do_userdel(self, arg):
        """Delete a user
        Usage: userdel <username>"""
        if not self.auth:
            print("Authentication system not available")
            return
        
        current_user = self.auth.get_current_user()
        if not current_user or current_user.role.value != "root":
            print("userdel: Permission denied")
            return
        
        username = arg.strip()
        if not username:
            print("Usage: userdel <username>")
            return
        
        try:
            if self.auth.delete_user(username):
                print(f"User {username} deleted")
            else:
                print(f"Failed to delete user {username}")
        except Exception as e:
            print(f"Error: {e}")
    
    def do_users(self, arg):
        """List all users"""
        if not self.auth:
            print("Authentication system not available")
            return
        
        users = self.auth.list_users()
        
        print(f"{'Username':<15} {'UID':<6} {'Role':<10} {'Home':<20} {'Groups'}")
        print("-" * 70)
        
        for user in users:
            groups_str = ",".join(user.groups[:3])
            if len(user.groups) > 3:
                groups_str += "..."
            
            print(f"{user.username:<15} {user.uid:<6} {user.role.value:<10} "
                  f"{user.home_dir:<20} {groups_str}")
    
    def do_su(self, arg):
        """Switch user
        Usage: su [username]"""
        if not self.auth:
            print("Authentication system not available")
            return
        
        # Default to root if no username given
        username = arg.strip() if arg else "root"
        
        current_user = self.auth.get_current_user()
        
        # Get password (unless current user is root)
        password = None
        if not current_user or current_user.role.value != "root":
            try:
                password = getpass.getpass(f"Password for {username}: ")
            except KeyboardInterrupt:
                print("\nSwitch user cancelled")
                return
        
        # Switch user
        if self.auth.switch_user(username, password):
            print(f"Switched to {username}")
            # Update prompt
            self.prompt = f"{username}@kos:{self.cwd}> "
            # Change to user's home directory
            user = self.auth.get_current_user()
            if user and self.vfs.exists(user.home_dir):
                self.cwd = user.home_dir
        else:
            print("su: Authentication failed")
    
    def do_id(self, arg):
        """Display user and group IDs
        Usage: id [username]"""
        if not self.auth:
            print("Authentication system not available")
            return
        
        # Get target user
        if arg:
            username = arg.strip()
            if username not in self.auth.users:
                print(f"id: {username}: no such user")
                return
            user = self.auth.users[username]
        else:
            user = self.auth.get_current_user()
            if not user:
                print("Not logged in")
                return
        
        # Display info
        groups_str = ",".join([f"{g}({g})" for g in user.groups])
        print(f"uid={user.uid}({user.username}) gid={user.gid}({user.username}) groups={groups_str}")
    
    def do_groups(self, arg):
        """Display group memberships
        Usage: groups [username]"""
        if not self.auth:
            print("Authentication system not available")
            return
        
        # Get target user
        if arg:
            username = arg.strip()
            if username not in self.auth.users:
                print(f"groups: {username}: no such user")
                return
            user = self.auth.users[username]
        else:
            user = self.auth.get_current_user()
            if not user:
                print("Not logged in")
                return
        
        print(" ".join(user.groups))
    
    # Register commands using MethodType
    shell.do_login = types.MethodType(do_login, shell)
    shell.do_logout = types.MethodType(do_logout, shell)
    shell.do_whoami = types.MethodType(do_whoami, shell)
    shell.do_passwd = types.MethodType(do_passwd, shell)
    shell.do_useradd = types.MethodType(do_useradd, shell)
    shell.do_userdel = types.MethodType(do_userdel, shell)
    shell.do_users = types.MethodType(do_users, shell)
    shell.do_su = types.MethodType(do_su, shell)
    shell.do_id = types.MethodType(do_id, shell)
    shell.do_groups = types.MethodType(do_groups, shell)
# User Management in KOS

This guide covers user account management, permissions, and security in KOS.

## Table of Contents
- [User Accounts](#user-accounts)
- [User Groups](#user-groups)
- [File Permissions](#file-permissions)
- [Sudo and Root Access](#sudo-and-root-access)
- [Password Management](#password-management)
- [User Sessions](#user-sessions)
- [Security Best Practices](#security-best-practices)

## User Accounts

### Viewing User Information
```bash
# Show current user
$ whoami

# Show detailed user information
$ id

# Show all logged-in users
$ who
$ w

# Show user login history
$ last
```

### Creating and Managing Users
```bash
# Create new user (requires root)
$ sudo useradd -m username
$ sudo passwd username

# Set user information
$ sudo chfn username

# Delete user
$ sudo userdel -r username  # -r removes home directory

# Modify user properties
$ sudo usermod [options] username
  -aG groupname  # Add to supplementary group
  -s /bin/bash   # Change login shell
  -d /new/home   # Change home directory
  -e YYYY-MM-DD  # Set account expiration date
```

## User Groups

### Managing Groups
```bash
# List all groups
$ getent group

# Create new group
$ sudo groupadd groupname

# Delete group
$ sudo groupdel groupname

# Add user to group
$ sudo usermod -aG groupname username

# Remove user from group
$ sudo deluser username groupname

# Change primary group
$ sudo usermod -g groupname username
```

### Viewing Group Membership
```bash
# Show groups current user belongs to
$ groups

# Show groups for specific user
$ groups username

# Show group information
$ getent group groupname
```

## File Permissions

### Understanding Permissions
```
-rwxr-xr-- 1 user group 1234 Jan 1 12:00 file
| |  |  |  |   |    |     |      |
| |  |  |  |   |    |     |      +-- File name
| |  |  |  |   |    |     +--------- Size in bytes
| |  |  |  |   |    +--------------- Group
| |  |  |  |   +-------------------- Owner
| |  |  |  +------------------------ Number of hard links
| |  |  +--------------------------- Others: r-- (read-only)
| |  +------------------------------ Group: r-x (read/execute)
| +--------------------------------- User: rwx (read/write/execute)
+------------------------------------ File type (- = file, d = directory, l = link)
```

### Special Permissions
```bash
# Set SUID (runs as file owner)
$ chmod u+s file

# Set SGID (runs as group owner)
$ chmod g+s file

# Set sticky bit (restrict file deletion)
$ chmod +t directory
```

## Sudo and Root Access

### Sudo Configuration
```bash
# Edit sudoers file (always use visudo)
$ sudo visudo

# Run command as another user
$ sudo -u username command

# Open root shell
$ sudo -i
$ sudo -s
```

### Example sudoers Entry
```
# Allow user to run all commands as root
username ALL=(ALL:ALL) ALL

# Allow group to run specific commands
%admin ALL=(ALL) /usr/bin/apt, /usr/bin/apt-get

# Allow passwordless sudo
username ALL=(ALL) NOPASSWD: ALL
```

## Password Management

### Changing Passwords
```bash
# Change your own password
$ passwd

# Change another user's password (root only)
$ sudo passwd username

# Force password change on next login
$ sudo passwd -e username

# Lock/unlock user account
$ sudo passwd -l username  # Lock
$ sudo passwd -u username  # Unlock
```

### Password Policies
```bash
# Set password expiration
$ sudo chage -M 90 username  # Max days
$ sudo chage -m 7 username   # Min days
$ sudo chage -W 7 username   # Warning days

# View password expiration
$ chage -l username
```

## User Sessions

### Managing Sessions
```bash
# List logged-in users
$ who
$ w

# Show login history
$ last
$ last username

# Send message to all users
$ wall "System maintenance in 5 minutes"

# Show user processes
$ ps -u username

# Kill user's processes
$ sudo pkill -u username
$ sudo killall -u username
```

### Session Security
```bash
# View failed login attempts
$ sudo lastb

# View authentication logs
$ sudo tail -f /var/log/auth.log

# Lock screen
$ xdg-screensaver lock
```

## Security Best Practices

### Account Security
1. Use strong, unique passwords
2. Implement password policies
3. Use SSH keys instead of passwords
4. Disable root login over SSH
5. Use sudo instead of logging in as root

### File System Security
1. Follow principle of least privilege
2. Set appropriate file permissions
3. Use groups to manage access
4. Regularly audit file permissions
5. Use ACLs for complex permission requirements

### System Hardening
```bash
# Remove unnecessary users
$ sudo userdel username

# Disable password login (SSH)
# Edit /etc/ssh/sshd_config
PasswordAuthentication no

# Install and configure fail2ban
$ sudo apt install fail2ban
```

## Troubleshooting

### Common Issues

1. **Permission Denied**
   - Check file permissions and ownership
   - Verify group membership with `groups`
   - Check for ACLs with `getfacl`

2. **User Cannot Log In**
   - Check if account is locked: `passwd -S username`
   - Check shell in /etc/passwd
   - Check for .nologin file in home directory

3. **Sudo Access Issues**
   - Verify user is in sudo group
   - Check /etc/sudoers for correct permissions
   - Check system logs: `sudo journalctl -xe`

4. **Password Reset**
   - Boot into recovery mode
   - Remount filesystem as read-write: `mount -o remount,rw /`
   - Change password: `passwd username`

## Advanced Topics

### Pluggable Authentication Modules (PAM)
```bash
# PAM configuration files
/etc/pam.d/
  - login
  - sudo
  - sshd

# Test PAM configuration
$ pam-auth-update
```

### Lightweight Directory Access Protocol (LDAP)
```bash
# Install LDAP client
$ sudo apt install libnss-ldap libpam-ldap nscd

# Configure LDAP client
$ sudo dpkg-reconfigure ldap-auth-config
```

### Access Control Lists (ACLs)
```bash
# Install ACL utilities
$ sudo apt install acl

# Set ACL
$ setfacl -m u:username:rwx file
$ setfacl -m g:groupname:rx directory

# View ACL
$ getfacl file

# Remove ACL
$ setfacl -x u:username file
```

## See Also

- [File System Guide](./filesystem.md)
- [Process Management](./process-management.md)
- [Package Management](./package-management.md)

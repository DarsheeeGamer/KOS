# User Management

This guide covers user account management, including creating, modifying, and managing user accounts and groups in KOS.

## User Accounts

### View Current User

Display information about the currently logged-in user:

```bash
whoami
```

### List Logged-in Users

Show all currently logged-in users:

```bash
who
```

### View User Information

Display detailed user information:

```bash
id username
```

### Creating Users

#### Add a New User

```bash
useradd username
```

#### Set User Password

```bash
passwd username
```

#### Create User with Home Directory

```bash
useradd -m username
```

#### Create User with Specific UID

```bash
useradd -u 1001 username
```

### Modifying Users

#### Change User Password

```bash
passwd username
```

#### Change User Shell

```bash
chsh -s /bin/bash username
```

#### Change User Home Directory

```bash
usermod -d /new/home/dir username
```

### Deleting Users

#### Remove User (Keep Home Directory)

```bash
userdel username
```

#### Remove User and Home Directory

```bash
userdel -r username
```

## Group Management

### List All Groups

```bash
cat /etc/group
```

### Create a New Group

```bash
groupadd groupname
```

### Add User to Group

```bash
usermod -aG groupname username
```

### Remove User from Group

```bash
gpasswd -d username groupname
```

### Delete a Group

```bash
groupdel groupname
```

## File Permissions

### View File Permissions

```bash
ls -l filename
```

### Change File Owner

```bash
chown username:groupname filename
```

### Change File Permissions

```bash
chmod 755 filename
```

## Sudo Access

### Grant Sudo Privileges

Add user to the sudo group:

```bash
usermod -aG sudo username
```

### Edit Sudoers File

```bash
visudo
```

Add the following line to grant full sudo access:
```
username ALL=(ALL:ALL) ALL
```

## User Sessions

### View User Sessions

```bash
who -a
```

### Terminate User Session

```bash
pkill -KILL -u username
```

## Password Policies

### Set Password Expiration

```bash
chage -M 90 username  # Password expires in 90 days
```

### Force Password Change on Next Login

```bash
chage -d 0 username
```

## Security Best Practices

1. Always use strong passwords
2. Regularly audit user accounts
3. Remove or disable unused accounts
4. Use the principle of least privilege
5. Regularly review sudo access
6. Implement password policies
7. Monitor login attempts
8. Use SSH keys instead of passwords when possible

## User Environment

### View User Environment Variables

```bash
printenv
```

### Set User Environment Variables

For current session:
```bash
export VARIABLE=value
```

Permanently (add to ~/.bashrc or ~/.profile):
```bash
echo 'export VARIABLE=value' >> ~/.bashrc
source ~/.bashrc
```

### User Limits

View current limits:
```bash
ulimit -a
```

Set file descriptor limit:
```bash
ulimit -n 4096
```

## User Authentication

### View Authentication Logs

```bash
cat /var/log/auth.log
```

### View Failed Login Attempts

```bash
grep 'Failed password' /var/log/auth.log
```

### Lock/Unlock User Account

Lock account:
```bash
passwd -l username
```

Unlock account:
```bash
passwd -u username
```

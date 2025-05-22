# First Steps with KOS

Welcome to the Kernel Operating System (KOS)! This guide will help you get started with the basic operations and features of KOS.

## Table of Contents
- [Starting KOS](#starting-kos)
- [Basic Navigation](#basic-navigation)
- [File Operations](#file-operations)
- [System Information](#system-information)
- [User Management](#user-management)
- [Process Management](#process-management)
- [Networking](#networking)
- [Package Management](#package-management)
- [Getting Help](#getting-help)

## Starting KOS

### Prerequisites
- Python 3.8 or higher
- Git (for cloning the repository)
- Basic command-line knowledge

### Installation
1. Clone the KOS repository:
   ```bash
   git clone https://github.com/DarsheeeGamer/KOS.git
   cd KOS
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Start KOS:
   ```bash
   python -m kos
   ```

You should see the KOS prompt:
```
kos@system:~$ 
```

## Basic Navigation

### Current Directory
```bash
# Print working directory
pwd

# List directory contents
ls          # Basic listing
ls -l       # Detailed listing
ls -la      # Include hidden files
ls -lh      # Human-readable sizes
```

### Changing Directories
```bash
cd /path/to/directory    # Absolute path
cd relative/path         # Relative path
cd ..                    # Up one level
cd ~                     # Home directory
cd -                     # Previous directory
cd /                     # Root directory
```

### Creating Directories
```bash
mkdir directory_name
mkdir -p path/to/directory  # Create parent directories
```

## File Operations

### Viewing Files
```bash
cat filename        # View entire file
less filename      # View file with pagination
head -n 10 file    # View first 10 lines
tail -n 10 file    # View last 10 lines
tail -f logfile    # Follow file in real-time
```

### File Manipulation
```bash
# Create/Edit files
nano filename      # Simple text editor

# Copy files
cp source destination
cp -r dir1 dir2    # Recursive copy

# Move/Rename files
mv oldname newname
mv file /new/path/

# Remove files/directories
rm filename
rm -r directory    # Recursive remove
rm -f file         # Force remove
```

### File Permissions
```bash
chmod 755 file     # Set permissions (rwxr-xr-x)
chmod +x script    # Make file executable
chown user:group file
```

## System Information

### System Status
```bash
uname -a           # Kernel information
hostname           # System hostname
whoami             # Current user
date               # Current date and time
uptime             # System uptime
```

### Hardware Information
```bash
lscpu              # CPU information
free -h            # Memory usage
lsblk              # Block devices
df -h              # Disk space
```

## User Management

### User Accounts
```bash
who                # Show logged in users
id                 # Current user info
sudo useradd username
sudo passwd username
sudo userdel username
```

### Groups
```bash
groups             # Current user's groups
sudo groupadd groupname
sudo usermod -aG groupname username
```

## Process Management

### Viewing Processes
```bash
ps                 # Current processes
ps aux             # All processes
top                # Interactive process viewer
htop               # Enhanced top (if installed)
```

### Managing Processes
```bash
kill PID           # Terminate process
kill -9 PID        # Force terminate
killall process_name
pkill pattern
```

### Background Jobs
```bash
command &          # Run in background
jobs               # List background jobs
fg %1              # Bring job to foreground
bg %1              # Run in background
```

## Networking

### Network Configuration
```bash
ip addr show       # Network interfaces
ip route           # Routing table
ping host          # Test connectivity
```

### Network Tools
```bash
netstat -tuln      # Listening ports
ss -tuln           # Modern alternative
curl ifconfig.me   # Public IP
wget url           # Download file
```

## Package Management

### List Packages
```bash
kpm list           # Installed packages
kpm search term    # Search packages
```

### Install/Remove Packages
```bash
kpm install package_name
kpm remove package_name
kpm update         # Update package list
kpm upgrade        # Upgrade all packages
```

### System Updates
```bash
kpm update
kpm upgrade
```

## Getting Help

### Built-in Help
```bash
command --help     # Most commands
man command        # Manual pages
info command       # Info pages
```

### KOS Documentation
```bash
man kos            # KOS manual
help               # Built-in help
```

### Online Resources
- [Official Documentation](https://github.com/DarsheeeGamer/KOS)
- [GitHub Issues](https://github.com/DarsheeeGamer/KOS/issues)
- [Community Forum](#) (if available)

## Next Steps

Now that you're familiar with the basics, you might want to explore:

1. [Shell Scripting](../user-guide/shell-scripting.md)
2. [User Management](../user-guide/user-management.md)
3. [Process Management](../user-guide/process-management.md)
4. [Networking](../user-guide/networking.md)

If you encounter any issues, please refer to the [troubleshooting guide](#) or [open an issue](https://github.com/DarsheeeGamer/KOS/issues) on GitHub.

## Getting Help

### List Available Commands
```bash
help
```

### Get Help on a Specific Command
```bash
help command_name
```

## Basic File Operations

### View File Contents
```bash
cat filename
```

### Create a Directory
```bash
mkdir directory_name
```

### Create a File
```bash
touch filename
```

### Copy Files
```bash
cp source destination
```

### Move/Rename Files
```bash
mv source destination
```

### Remove Files
```bash
rm filename
rm -r directory_name  # Remove directory recursively
```

## User Management

### View Current User
```bash
whoami
```

### Switch User
```bash
su username
```

## Exiting KOS

To exit KOS, type:
```bash
exit
```

## Next Steps

Now that you've learned the basics, you might want to:

1. Explore the [User Guide](../user-guide/README.md) for more detailed information
2. Learn about [package management](../user-guide/package-management.md)
3. Check out [advanced features](../advanced/README.md)

Remember, you can always type `help` in the KOS shell to see available commands and get help.

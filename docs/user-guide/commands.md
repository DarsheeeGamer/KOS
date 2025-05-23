# KOS Command Reference

This document provides a comprehensive reference for all available commands in KOS, organized by category.

## File Operations

### `ls` - List Directory Contents

List files and directories in the current directory.

**Usage:**
```bash
ls [options] [path]
```

**Options:**
- `-l`: Use long listing format
- `-a`: Show hidden files
- `-h`: Human-readable file sizes
- `-r`: Reverse sort order
- `-t`: Sort by modification time

### `cd` - Change Directory

Change the current working directory.

**Usage:**
```bash
cd [directory]
```

### `pwd` - Print Working Directory

Display the current working directory path.

**Usage:**
```bash
pwd
```

### `touch` - Create Empty File

Create a new empty file or update file timestamps.

**Usage:**
```bash
touch filename
```

### `cat` - Display File Contents

Display the contents of a file.

**Usage:**
```bash
cat filename
```

### `mkdir` - Create Directory

Create a new directory.

**Usage:**
```bash
mkdir directory_name
```

### `rm` - Remove Files or Directories

Remove files or directories.

**Usage:**
```bash
rm [options] file...
```

**Options:**
- `-r`: Remove directories and their contents recursively
- `-f`: Force removal without confirmation

### `cp` - Copy Files or Directories

Copy files or directories.

**Usage:**
```bash
cp [options] source destination
```

### `mv` - Move or Rename Files

Move or rename files and directories.

**Usage:**
```bash
mv source destination
```

## Process Management

### `ps` - List Processes

List currently running processes.

**Usage:**
```bash
ps
```

### `kill` - Terminate Processes

Terminate a running process.

**Usage:**
```bash
kill [signal] pid
```

### `top` - Display Processes

Display and update sorted information about processes.

**Usage:**
```bash
top
```

## System Information

### `whoami` - Display Current User

Display the current user name.

**Usage:**
```bash
whoami
```

### `hostname` - Display System Hostname

Display or set the system hostname.

**Usage:**
```bash
hostname [new_hostname]
```

### `df` - Disk Space Usage

Show disk space usage.

**Usage:**
```bash
df [options]
```

## Package Management

### `install` - Install Packages

Install a new package.

**Usage:**
```bash
install package_name
```

### `uninstall` - Remove Packages

Remove an installed package.

**Usage:**
```bash
uninstall package_name
```

### `list` - List Installed Packages

List all installed packages.

**Usage:**
```bash
list
```

## Getting Help

### `help` - Display Help

Display help information.

**Usage:**
```bash
help [command]
```

### `man` - Display Manual Pages

Display the manual page for a command.

**Usage:**
```bash
man command
```

## Exiting KOS

### `exit` - Exit the Shell

Exit the KOS shell.

**Usage:**
```bash
exit
```

## Advanced Usage

For more detailed information about each command, including additional options, use the `help` command followed by the command name.

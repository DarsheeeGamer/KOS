# KOS File System Guide

This guide covers the KOS file system structure, navigation, and file operations.

## Table of Contents
- [File System Structure](#file-system-structure)
- [Basic Navigation](#basic-navigation)
- [File Operations](#file-operations)
- [Permissions](#permissions)
- [Special Directories](#special-directories)
- [Advanced Topics](#advanced-topics)

## File System Structure

KOS uses a hierarchical file system with the following key directories:

- `/` - Root directory
  - `/bin` - Essential command binaries
  - `/boot` - Boot loader files
  - `/dev` - Device files
  - `/etc` - System configuration files
  - `/home` - User home directories
  - `/lib` - Essential shared libraries
  - `/mnt` - Mount points for temporary mounts
  - `/proc` - Virtual filesystem for process information
  - `/root` - Root user's home directory
  - `/sbin` - System binaries
  - `/tmp` - Temporary files
  - `/usr` - User programs and utilities
  - `/var` - Variable data files

## Basic Navigation

### Current Directory
```bash
# Print working directory
$ pwd

# List directory contents
$ ls [options] [directory]
  -l: Long format
  -a: Show hidden files
  -h: Human-readable sizes
  -R: Recursive listing
```

### Changing Directories
```bash
# Change to home directory
$ cd
$ cd ~

# Change to specific directory
$ cd /path/to/directory

# Go up one directory
$ cd ..

# Go to previous directory
$ cd -
```

## File Operations

### Viewing Files
```bash
# View entire file
$ cat filename

# View file with paging
$ less filename
$ more filename

# View beginning of file
$ head [-n lines] filename

# View end of file
$ tail [-n lines] filename
  -f: Follow file changes
```

### Creating Files and Directories
```bash
# Create empty file
$ touch filename

# Create directory
$ mkdir directory_name
  -p: Create parent directories

# Create multiple directories
$ mkdir -p dir1/dir2/dir3
```

### Copying, Moving, and Renaming
```bash
# Copy file
$ cp source destination
  -r: Recursive (for directories)
  -v: Verbose

# Move/rename file
$ mv oldname newname
$ mv file /new/location/
```

### Deleting Files and Directories
```bash
# Remove file
$ rm filename
  -f: Force removal
  -i: Interactive mode

# Remove directory
$ rmdir directory_name  # Empty directory
$ rm -r directory_name  # Recursive remove
```

## Permissions

### Viewing Permissions
```bash
$ ls -l
-rwxr-xr-x 1 user group 1234 Jan 1 12:00 filename
  u g o
  | | |
  | | +-- Others: read, execute
  | +---- Group: read, execute
  +------- User: read, write, execute
```

### Changing Permissions
```bash
# Symbolic mode
$ chmod u+x filename     # Add execute for user
$ chmod go-w filename    # Remove write for group and others
$ chmod a=rw filename    # Set read/write for all

# Numeric mode
$ chmod 755 filename     # rwxr-xr-x
$ chmod 644 filename     # rw-r--r--
```

### Changing Ownership
```bash
# Change owner
$ chown user:group filename

# Recursive ownership change
$ chown -R user:group directory
```

## Special Directories

### /proc Filesystem
```bash
# View system information
$ cat /proc/cpuinfo
$ cat /proc/meminfo
$ cat /proc/version

# Process information
$ ls /proc/[0-9]*/  # List all processes
```

### /dev Directory
```bash
# List block devices
$ lsblk

# List USB devices
$ lsusb

# List PCI devices
$ lspci
```

## Advanced Topics

### Finding Files
```bash
# Find files by name
$ find /path -name "*.txt"

# Find files by type
$ find /path -type f -name "*.conf"

# Find files by size
$ find /path -size +10M
```

### Disk Usage
```bash
# Show disk usage
$ df -h

# Show directory sizes
$ du -sh /path/to/directory

# Interactive disk usage analyzer
$ ncdu
```

### File Compression
```bash
# Create archive
$ tar -czvf archive.tar.gz /path/to/directory

# Extract archive
$ tar -xzvf archive.tar.gz

# View archive contents
$ tar -tzvf archive.tar.gz
```

### Symbolic Links
```bash
# Create symbolic link
$ ln -s /path/to/target /path/to/link

# View link target
$ ls -l /path/to/link
$ readlink /path/to/link
```

## Troubleshooting

### Common Issues

1. **Permission Denied**
   - Check file permissions with `ls -l`
   - Use `sudo` if you need root privileges
   - Check file ownership with `ls -l`

2. **No Such File or Directory**
   - Check for typos in the path
   - Use absolute paths when in doubt
   - Check if the file exists with `ls -l /path/to/file`

3. **File System Full**
   - Check disk usage with `df -h`
   - Find large files with `find / -type f -size +100M -exec ls -lh {} \;`

4. **Broken Symbolic Links**
   - Find broken links: `find /path -xtype l`
   - Remove broken links: `find /path -xtype l -delete`

## Best Practices

1. **File Naming**
   - Use only alphanumeric characters, dots, hyphens, and underscores
   - Avoid spaces in filenames (use underscores instead)
   - Be descriptive but concise

2. **Directory Structure**
   - Keep related files together
   - Use subdirectories to organize large numbers of files
   - Follow the Filesystem Hierarchy Standard (FHS)

3. **Permissions**
   - Follow the principle of least privilege
   - Use groups to manage access for multiple users
   - Be careful with setuid/setgid bits

4. **Backups**
   - Regularly back up important files
   - Test your backups
   - Consider using version control for configuration files

## See Also

- [Basic Commands](./basic-commands.md)
- [Process Management](./process-management.md)
- [User Management](./user-management.md)

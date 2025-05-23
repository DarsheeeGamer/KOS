# File System Guide

This guide explains the KOS file system structure and how to work with files and directories.

## File System Structure

KOS follows a Unix-like file system hierarchy:

- `/` - Root directory
  - `/bin` - Essential command binaries
  - `/etc` - System configuration files
  - `/home` - User home directories
  - `/tmp` - Temporary files
  - `/usr` - User programs and data
  - `/var` - Variable data files

## Working with Files and Directories

### Creating Files and Directories

Create a new file:
```bash
touch filename.txt
```

Create a new directory:
```bash
mkdir directory_name
```

Create nested directories:
```bash
mkdir -p path/to/directory
```

### Viewing and Editing Files

View file contents:
```bash
cat filename.txt
```

View file with pagination:
```bash
less filename.txt
```

Edit a file (requires a text editor):
```bash
edit filename.txt
```

### Copying, Moving, and Renaming

Copy a file:
```bash
cp source.txt destination.txt
```

Move or rename a file:
```bash
mv oldname.txt newname.txt
```

### Deleting Files and Directories

Delete a file:
```bash
rm file.txt
```

Delete a directory and its contents:
```bash
rm -r directory_name
```

## File Permissions

KOS uses Unix-style file permissions. View permissions with:
```bash
ls -l
```

Change file permissions:
```bash
chmod 755 filename
```

Change file ownership:
```bash
chown user:group filename
```

## Disk Usage

View disk usage for the current directory:
```bash
du -sh
```

View disk space usage for all mounted filesystems:
```bash
df -h
```

## Finding Files

Find files by name:
```bash
find /path -name "*.txt"
```

Search for text in files:
```bash
grep "search term" /path/to/search
```

## Symbolic Links

Create a symbolic link:
```bash
ln -s /path/to/original /path/to/link
```

## File Compression

Create a compressed archive:
```bash
tar -czvf archive.tar.gz /path/to/directory
```

Extract a compressed archive:
```bash
tar -xzvf archive.tar.gz
```

## Best Practices

1. Use meaningful file and directory names
2. Organize files in a logical directory structure
3. Regularly back up important files
4. Be cautious with recursive operations (rm -r, chmod -R, etc.)
5. Use file permissions to control access to sensitive files

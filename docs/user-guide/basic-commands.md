# Basic Commands

This guide covers the essential commands for navigating and using KOS.

## Navigation

### `ls` - List Directory Contents

List files and directories in the current directory.

**Usage:**
```bash
ls [options] [directory]
```

**Options:**
- `-l`: Long format (detailed listing)
- `-a`: Show hidden files
- `-h`: Human-readable file sizes

**Examples:**
```bash
ls          # List files in current directory
ls -la      # Detailed listing including hidden files
ls /path    # List files in /path
```

### `cd` - Change Directory

Change the current working directory.

**Usage:**
```bash
cd [directory]
```

**Special Directories:**
- `.`: Current directory
- `..`: Parent directory
- `~`: Home directory
- `/`: Root directory

**Examples:**
```bash
cd /path/to/dir  # Change to specific directory
cd ..            # Move up one directory
cd ~             # Go to home directory
cd /             # Go to root directory
```

### `pwd` - Print Working Directory

Display the current working directory.

**Usage:**
```bash
pwd
```

## File Operations

### `cat` - View File Contents

Display the contents of a file.

**Usage:**
```bash
cat <file>
```

**Examples:**
```bash
cat file.txt
```

### `touch` - Create Empty File

Create a new empty file or update file timestamps.

**Usage:**
```bash
touch <file>
```

**Examples:**
```bash
touch newfile.txt
```

### `mkdir` - Create Directory

Create a new directory.

**Usage:**
```bash
mkdir <directory>
```

**Options:**
- `-p`: Create parent directories as needed

**Examples:**
```bash
mkdir newdir
mkdir -p path/to/directory
```

### `cp` - Copy Files/Directories

Copy files and directories.

**Usage:**
```bash
cp [options] <source> <destination>
```

**Options:**
- `-r`: Copy directories recursively
- `-v`: Verbose output

**Examples:**
```bash
cp file.txt /backup/
cp -r dir1/ dir2/
```

### `mv` - Move/Rename Files

Move or rename files and directories.

**Usage:**
```bash
mv <source> <destination>
```

**Examples:**
```bash
mv old.txt new.txt     # Rename file
mv file.txt dir/       # Move file to directory
```

### `rm` - Remove Files/Directories

Remove files or directories.

**Usage:**
```bash
rm [options] <file/directory>
```

**Options:**
- `-r`: Remove directories and their contents
- `-f`: Force removal without confirmation
- `-i`: Prompt before removal

**Examples:**
```bash
rm file.txt
rm -r directory/
rm -rf directory/  # Dangerous! Force recursive removal
```

## System Information

### `whoami` - Show Current User

Display the current username.

**Usage:**
```bash
whoami
```

### `hostname` - Show System Hostname

Display or set the system hostname.

**Usage:**
```bash
hostname [new_hostname]
```

### `date` - Show System Date/Time

Display or set the system date and time.

**Usage:**
```bash
date [MMDDhhmm[[CC]YY][.ss]]
```

**Examples:**
```bash
date                    # Show current date/time
date 052522302025.00    # Set date/time to May 25, 2025, 23:00:00
```

## Getting Help

### `help` - Show Help

Display help information about commands.

**Usage:**
```bash
help [command]
```

**Examples:**
```bash
help        # List all commands
help ls     # Show help for ls command
```

### `man` - Manual Pages

Display manual pages for commands.

**Usage:**
```bash
man <command>
```

**Examples:**
```bash
man ls
```

## Process Management

### `ps` - Process Status

Display information about running processes.

**Usage:**
```bash
ps [options]
```

**Options:**
- `-e`: Show all processes
- `-f`: Full format listing

### `kill` - Terminate Processes

Send signals to processes.

**Usage:**
```bash
kill [options] <pid>
```

**Common Signals:**
- `SIGTERM` (15): Terminate gracefully (default)
- `SIGKILL` (9): Force terminate

**Examples:**
```bash
kill 1234          # Send SIGTERM to process 1234
kill -9 1234       # Force kill process 1234
kill -SIGKILL 1234 # Same as above
```

## Package Management

### `kpm` - KOS Package Manager

Manage software packages.

**Usage:**
```bash
kpm <command> [options]
```

**Common Commands:**
```bash
kpm update              # Update package lists
kpm install <package>   # Install a package
kpm remove <package>    # Remove a package
kpm list                # List installed packages
kpm search <query>      # Search for packages
```

## Exiting KOS

### `exit` - Exit the Shell

Exit the KOS shell.

**Usage:**
```bash
exit
```

## Tips and Tricks

1. **Command History**:
   - Use ↑/↓ arrow keys to navigate command history
   - `history` to view command history
   - `!<number>` to repeat a command from history

2. **Tab Completion**:
   - Press Tab to auto-complete commands and file/directory names

3. **Command Chaining**:
   - `command1 ; command2`: Run commands sequentially
   - `command1 && command2`: Run command2 only if command1 succeeds
   - `command1 || command2`: Run command2 only if command1 fails
   - `command1 | command2`: Pipe output of command1 to command2

4. **Redirection**:
   - `command > file`: Redirect output to file (overwrite)
   - `command >> file`: Append output to file
   - `command < file`: Use file as input
   - `command 2> file`: Redirect stderr to file

5. **Aliases**:
   - Create shortcuts for frequently used commands
   ```bash
   alias ll='ls -la'
   alias ..='cd ..'
   ```

## Next Steps

- [File System](./filesystem.md) - Learn about KOS file system organization
- [Package Management](./package-management.md) - Install and manage software
- [User Management](./user-management.md) - Manage users and permissions

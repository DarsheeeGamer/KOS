# KOS Basic Commands Reference

This comprehensive guide covers all essential commands for effectively using KOS. Each command includes detailed usage, common options, and practical examples.

## Table of Contents
- [File System Navigation](#file-system-navigation)
- [File Operations](#file-operations)
- [Text Processing](#text-processing)
- [System Information](#system-information)
- [Process Management](#process-management)
- [User Management](#user-management)
- [Networking](#networking)
- [Package Management](#package-management)
- [Searching](#searching)
- [Compression](#compression)
- [File Permissions](#file-permissions)
- [Command Chaining](#command-chaining)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Command History](#command-history)
- [Environment Variables](#environment-variables)
- [Aliases](#aliases)
- [Exit Codes](#exit-codes)

## File System Navigation

### `pwd` - Print Working Directory

Display the full path of the current working directory.

**Usage:**
```bash
pwd [options]
```

**Options:**
- `-L`: (Default) Print the logical current directory
- `-P`: Print the physical directory (resolves symlinks)

**Examples:**
```bash
pwd         # /home/username
cd /var/www
pwd         # /var/www
```

### `ls` - List Directory Contents

List information about files and directories.

**Usage:**
```bash
ls [options] [file/directory...]
```

**Common Options:**
- `-a, --all`: Show hidden files (starting with .)
- `-l`: Use long listing format
- `-h, --human-readable`: Print sizes in human readable format (e.g., 1K, 234M, 2G)
- `-t`: Sort by modification time, newest first
- `-r, --reverse`: Reverse order while sorting
- `-S`: Sort by file size, largest first
- `-R, --recursive`: List subdirectories recursively
- `--color[=WHEN]`: Colorize the output (always/never/auto)

**Examples:**
```bash
ls -lah              # Detailed human-readable list with hidden files
ls -lS /etc          # List /etc by file size
ls -t | head -5      # 5 most recently modified files
ls -d */             # List only directories
ls -l --time-style=long-iso  # ISO date format
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
- `~` or `~username`: Home directory of current user or specified user
- `-`: Previous working directory
- `/`: Root directory

**Environment Variables:**
- `CDPATH`: Colon-separated list of directories to search
- `HOME`: Default directory if no arguments provided
- `OLDPWD`: Previous working directory

**Examples:**
```bash
cd /var/www/html     # Absolute path
cd ../relative/path  # Relative path
cd ~/Documents      # Home directory
cd -                 # Switch to previous directory
cd                   # Go to home directory
```

### `pushd`, `popd`, `dirs` - Directory Stack

Manage a stack of directories for quick navigation.

**Usage:**
```bash
pushd [directory]
popd [options]
dirs [options]
```

**Options for popd:**
- `-n`: Don't change directory
- `-q`: Quiet mode, don't print directory stack

**Options for dirs:**
- `-c`: Clear directory stack
- `-l`: Expand ~ to home directory
- `-p`: One directory per line
- `-v`: One directory per line with indices

**Examples:**
```bash
pushd /var/log      # Add /var/log to stack and cd to it
pushd +2            # Rotate stack to bring 3rd directory to top
popd                # Go to previous directory and remove from stack
dirs -v             # Show directory stack with indices
```

### `tree` - List Directory Contents in Tree-like Format

**Installation:**
```bash
# Ubuntu/Debian
sudo apt install tree

# RHEL/CentOS
sudo yum install tree

# macOS
brew install tree
```

**Usage:**
```bash
tree [options] [directory]
```

**Options:**
- `-a`: Show hidden files
- `-d`: List directories only
- `-f`: Print full path prefix
- `-L level`: Max display depth
- `-P pattern`: List files matching pattern
- `-I pattern`: Exclude files matching pattern
- `-h`: Print sizes in human readable format
- `--du`: Show directory size

**Examples:**
```bash
tree -L 2           # Show 2 levels deep
tree -d             # Show directories only
tree -h --du        # Show sizes in human readable format
tree -P '*.py'      # Show only Python files
```

## File Operations

### `cp` - Copy Files and Directories

**Usage:**
```bash
cp [options] source... destination
```

**Common Options:**
- `-i`: Interactive mode (prompt before overwrite)
- `-r, -R`: Copy directories recursively
- `-v`: Verbose output
- `-p`: Preserve file attributes
- `-a`: Archive mode (preserve permissions, ownership, timestamps)
- `-n`: No clobber (don't overwrite existing)
- `-u`: Copy only when source is newer

**Examples:**
```bash
cp file1.txt file2.txt     # Copy file
cp -r dir1/ dir2/         # Copy directory
cp -p file1.txt /backup/  # Preserve attributes
cp -u *.txt backup/      # Update only changed files
```

### `mv` - Move or Rename Files

**Usage:**
```bash
mv [options] source... destination
```

**Common Options:**
- `-i`: Prompt before overwrite
- `-n`: Don't overwrite existing
- `-v`: Verbose output
- `-u`: Move only when source is newer

**Examples:**
```bash
mv oldname newname        # Rename file
mv file.txt dir/         # Move file
mv -i *.txt ~/backup/    # Interactive move
```

### `rm` - Remove Files or Directories

**Usage:**
```bash
rm [options] file...
```

**Common Options:**
- `-f`: Force removal
- `-i`: Interactive mode
- `-r, -R`: Remove directories recursively
- `-v`: Verbose output

**Examples:**
```bash
rm file.txt              # Remove file
rm -r directory/         # Remove directory
rm -i *.tmp             # Interactive removal
rm -f /tmp/*.log        # Force remove
```

### `mkdir` - Create Directories

**Usage:**
```bash
mkdir [options] directory...
```

**Common Options:**
- `-p`: Create parent directories as needed
- `-m`: Set file mode (permissions)
- `-v`: Verbose output

**Examples:**
```bash
mkdir newdir
mkdir -p path/to/dir
mkdir -m 755 secure_dir
```

### `touch` - Create Empty Files or Update Timestamps

**Usage:**
```bash
touch [options] file...
```

**Common Options:**
- `-a`: Change only access time
- `-m`: Change only modification time
- `-t`: Use specific timestamp
- `-r`: Use another file's timestamp

**Examples:**
```bash
touch file.txt           # Create empty file
touch -t 202301011200 file.txt  # Set specific time
touch -r ref.txt file.txt  # Use reference file's timestamp
```

### `cat` - Concatenate and Display Files

**Usage:**
```bash
cat [options] [file...]
```

**Common Options:**
- `-n`: Number all output lines
- `-b`: Number non-empty output lines
- `-s`: Squeeze multiple adjacent empty lines
- `-v`: Display non-printing characters

**Examples:**
```bash
cat file.txt
cat -n file.txt
cat file1.txt file2.txt > combined.txt
```

### `less` - View File Contents with Navigation

**Usage:**
```bash
less [options] file
```

**Navigation Commands:**
- `Space`: Next page
- `b`: Previous page
- `g`: Go to start
- `G`: Go to end
- `/pattern`: Search forward
- `?pattern`: Search backward
- `n`: Next match
- `N`: Previous match
- `q`: Quit

**Examples:**
```bash
less large_file.log
less +F /var/log/syslog  # Follow mode (like tail -f)
```

### `head` and `tail` - View File Start/End

**Usage:**
```bash
head [options] [file...]
tail [options] [file...]
```

**Common Options:**
- `-n NUM`: Show NUM lines (default: 10)
- `-f`: Follow file changes (tail only)
- `-q`: Quiet mode
- `-v`: Verbose mode

**Examples:**
```bash
head -n 20 file.txt
tail -f /var/log/syslog  # Follow log file
tail -n +100 file.txt   # Start from line 100
```

### `file` - Determine File Type

**Usage:**
```bash
file [options] file...
```

**Examples:**
```bash
file document.pdf
file /bin/ls
```

### `stat` - Display File Status

**Usage:**
```bash
stat [options] file...
```

**Common Options:**
- `-c`: Custom output format
- `-f`: Display filesystem status
- `-t`: Display in terse format

**Examples:**
```bash
stat file.txt
stat -c "%A %n" *  # Permissions and filenames
```

### `ln` - Create Links

**Usage:**
```bash
# Hard link
ln source_file link_name

# Symbolic link
ln -s source_file link_name
```

**Examples:**
```bash
ln -s /path/to/original /path/to/link
ln file.txt hardlink.txt
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

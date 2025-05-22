# Process Management in KOS

This guide covers process management, monitoring, and job control in KOS.

## Table of Contents
- [Process Basics](#process-basics)
- [Process Monitoring](#process-monitoring)
- [Process Control](#process-control)
- [Job Control](#job-control)
- [System Resources](#system-resources)
- [Scheduling Tasks](#scheduling-tasks)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Process Basics

### What is a Process?
A process is an instance of a running program. Each process has:
- A unique Process ID (PID)
- A parent process (PPID)
- A user and group owner
- Resource limits and priorities
- Environment variables
- File descriptors

### Process States
- **Running (R)**: Currently executing
- **Sleeping (S)**: Waiting for an event
- **Stopped (T)**: Suspended by a signal
- **Zombie (Z)**: Terminated but not reaped by parent
- **Uninterruptible Sleep (D)**: Waiting for I/O

## Process Monitoring

### Basic Commands
```bash
# List all processes
$ ps aux
  a: Show processes for all users
  u: Display user-oriented format
  x: Include processes not attached to a terminal

# Process tree
$ pstree
  -p: Show PIDs
  -u: Show username
  -h: Highlight current process

# Interactive process viewer
$ top
  -d: Update delay (seconds)
  -p: Monitor specific PIDs
  -u: Show processes for specific user

# Improved top
$ htop
$ btop
```

### Finding Processes
```bash
# Find process by name
$ pgrep process_name
$ pidof process_name

# Find process using a file
$ lsof /path/to/file
$ fuser -v /path/to/file

# Find processes listening on ports
$ ss -tulnp
$ netstat -tulnp
```

## Process Control

### Starting Processes
```bash
# Run in foreground
$ command [arguments]

# Run in background
$ command &

$ nohup command &

$ disown
```

### Stopping Processes
```bash
# Graceful stop (SIGTERM)
$ kill PID
$ pkill process_name
$ killall process_name

# Force stop (SIGKILL)
$ kill -9 PID
$ pkill -9 process_name

# Stop process (SIGSTOP)
$ kill -STOP PID
```

### Process Priority
```bash
# Nice value range: -20 (highest) to 19 (lowest)

# Start process with nice value
$ nice -n 10 command

# Change nice value of running process
$ renice -n 5 -p PID

# View nice values
$ ps -o pid,ni,comm
```

## Job Control

### Managing Jobs
```bash
# List jobs
$ jobs
  -l: Include PIDs

# Bring job to foreground
$ fg %job_number

# Continue in background
$ bg %job_number

# Disown job (prevent HUP on logout)
$ disown %job_number
```

### No Hangup
```bash
# Run command immune to hangups
$ nohup command &


# Use screen or tmux for persistent sessions
$ screen
$ tmux
```

## System Resources

### Monitoring Resources
```bash
# CPU and memory usage
$ vmstat 1
$ mpstat 1
$ free -h

# I/O statistics
$ iostat -x 1
$ iotop

# Network usage
$ iftop
$ nethogs
```

### Process Limits
```bash
# View limits
$ ulimit -a

# Set limits for current session
$ ulimit -n 1024  # Open files
$ ulimit -u 1000  # User processes

# System-wide limits
/etc/security/limits.conf
```

## Scheduling Tasks

### Cron Jobs
```bash
# Edit crontab
$ crontab -e

# List crontab
$ crontab -l

# Remove crontab
$ crontab -r

# Example crontab entries
* * * * * command  # Every minute
0 * * * * command  # Every hour
0 0 * * * command  # Daily
0 0 * * 0 command  # Weekly
0 0 1 * * command  # Monthly
@reboot command    # On boot
```

### Systemd Timers
```bash
# List timers
$ systemctl list-timers

# Create a timer
/etc/systemd/system/mytimer.timer
[Unit]
Description=Run mytimer

[Timer]
OnBootSec=15min
OnUnitActiveSec=1d

[Install]
WantedBy=timers.target
```

## Troubleshooting

### Common Issues

1. **High CPU Usage**
   ```bash
   # Find CPU-intensive processes
   $ top -o %CPU
   $ ps -eo pid,ppid,cmd,%cpu --sort=-%cpu | head
   
   # Get thread details
   $ top -H -p PID
   $ ps -T -p PID
   ```

2. **High Memory Usage**
   ```bash
   # Find memory-hungry processes
   $ top -o %MEM
   $ ps -eo pid,ppid,cmd,%mem --sort=-%mem | head
   
   # Check for memory leaks
   $ pmap -x PID
   $ valgrind --tool=memcheck --leak-check=yes program
   ```

3. **Zombie Processes**
   ```bash
   # Find zombie processes
   $ ps aux | grep Z
   
   # Kill parent process
   $ kill -HUP PPID
   ```

4. **Stuck Processes**
   ```bash
   # Check for I/O wait
   $ iostat -x 1
   $ iotop -o
   
   # Check for disk space
   $ df -h
   $ du -sh /*
   ```

## Best Practices

### Process Management
1. Use `htop` for interactive process management
2. Prefer `pkill` and `killall` over manual PID lookup
3. Use `nohup`, `screen`, or `tmux` for long-running processes
4. Set appropriate process priorities with `nice` and `renice`
5. Monitor system resources regularly

### Job Scheduling
1. Use `cron` for regular tasks
2. Consider `systemd` timers for system services
3. Log all scheduled job output
4. Test cron jobs before deploying
5. Handle environment variables properly in cron jobs

### Resource Management
1. Set appropriate process limits
2. Monitor system resources
3. Use `ulimit` to prevent resource exhaustion
4. Consider using `cgroups` for resource control
5. Implement monitoring and alerting

## Advanced Topics

### Process Substitution
```bash
# Compare outputs
$ diff <(command1) <(command2)

# Process multiple files
$ while read line; do
    echo "Processing $line"
done < <(find /path -type f)
```

### Process Substitution with xargs
```bash
# Process files in parallel
$ find . -name '*.log' | xargs -P 4 -I {} gzip {}

# Handle filenames with spaces
$ find . -name '*.txt' -print0 | xargs -0 rm
```

### Systemd Service Management
```bash
# Create a service
/etc/systemd/system/myservice.service
[Unit]
Description=My Service

[Service]
ExecStart=/path/to/command
Restart=always
User=username

[Install]
WantedBy=multi-user.target

# Manage service
$ sudo systemctl daemon-reload
$ sudo systemctl start myservice
$ sudo systemctl enable myservice
```

## See Also
- [File System Guide](./filesystem.md)
- [User Management](./user-management.md)
- [Package Management](./package-management.md)

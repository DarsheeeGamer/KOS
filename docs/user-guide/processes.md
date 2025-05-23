# Process Management

This guide covers how to manage processes in KOS, including viewing, controlling, and monitoring running processes.

## Viewing Processes

### List All Processes

To list all running processes:

```bash
ps aux
```

This displays a detailed list of all processes with information such as:
- Process ID (PID)
- CPU and memory usage
- Command that started the process
- Process owner

### Filter Processes

To find a specific process:

```bash
ps aux | grep process_name
```

## Process Control

### Running Processes in the Background

Add `&` at the end of a command to run it in the background:

```bash
long_running_command &
```

### View Background Jobs

List all background jobs:

```bash
jobs
```

### Bring Job to Foreground

Bring a background job to the foreground:

```bash
fg %job_number
```

### Suspend a Process

Suspend the current foreground process by pressing `Ctrl+Z`.

### Terminating Processes

#### Graceful Termination

```bash
kill PID
```

#### Force Termination

```bash
kill -9 PID
```

#### Kill by Name

```bash
pkill process_name
```

## Process Monitoring

### Real-time Process Monitoring

Monitor processes in real-time:

```bash
top
```

Press `q` to quit.

### System Resource Usage

View system resource usage:

```bash
vmstat 1
```

### Process Tree

View the process hierarchy:

```bash
pstree
```

## Process Priority

### Change Process Priority

Set process priority (nice value ranges from -20 to 19, where -20 is highest priority):

```bash
nice -n 10 command
```

### Change Running Process Priority

```bash
renice -n 5 -p PID
```

## System Services

### List All Services

```bash
service --status-all
```

### Start a Service

```bash
service service_name start
```

### Stop a Service

```bash
service service_name stop
```

### Restart a Service

```bash
service service_name restart
```

## System Logs

View system logs:

```bash
cat /var/log/syslog
```

View kernel messages:

```bash
dmesg
```

## Process Management Best Practices

1. Always try to terminate processes gracefully before using force
2. Use `top` or `htop` to monitor system resources
3. Be cautious when changing process priorities
4. Check system logs when troubleshooting process issues
5. Use `nohup` for long-running processes that should continue after logout

## Advanced Process Management

### Process Groups

Send a signal to a process group:

```bash
kill -SIGNAL -PGID
```

### Process Substitution

Use process substitution to read from or write to a process:

```bash
diff <(command1) <(command2)
```

### Process Timeout

Run a command with a timeout:

```bash
timeout 5s long_running_command
```

This will terminate the command if it runs longer than 5 seconds.

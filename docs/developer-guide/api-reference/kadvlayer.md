# KADVLayer API Reference

The `KADVLayer` module provides advanced system integration capabilities for KOS, offering a comprehensive set of tools for system monitoring, process management, and resource utilization.

## Overview

`KADVLayer` is the main class that provides access to all advanced system integration features. It's designed to be thread-safe and provides event-based callbacks for system events.

## Core Components

### KADVLayer

Main class providing system integration capabilities.

#### Methods

##### `__init__(self, config: Optional[Dict] = None)`
Initialize the KADVLayer with optional configuration.

**Parameters**:
- `config` (Dict, optional): Configuration dictionary. Defaults to None.

**Example**:
```python
from kos.advanced import KADVLayer

# Initialize with default settings
kadv = KADVLayer()

# Initialize with custom settings
config = {
    "monitoring_interval": 5.0,
    "log_level": "INFO"
}
kadv = KADVLayer(config=config)
```

##### `start_monitoring(self) -> None`
Start monitoring system resources and processes.

**Raises**:
- `RuntimeError`: If monitoring is already running.

**Example**:
```python
kadv.start_monitoring()
```

##### `stop_monitoring(self) -> None`
Stop monitoring system resources and processes.

**Example**:
```python
kadv.stop_monitoring()
```

##### `get_system_info(self) -> Dict[str, Any]`
Get comprehensive system information.

**Returns**:
- `Dict[str, Any]`: Dictionary containing system information.

**Example**:
```python
system_info = kadv.get_system_info()
print(f"OS: {system_info['os']}")
print(f"CPU Cores: {system_info['cpu_cores']}")
print(f"Total Memory: {system_info['memory']['total']} MB")
```

##### `get_processes(self) -> List[Dict[str, Any]]`
Get information about all running processes.

**Returns**:
- `List[Dict[str, Any]]`: List of process information dictionaries.

**Example**:
```python
processes = kadv.get_processes()
for proc in processes[:5]:  # Show first 5 processes
    print(f"PID: {proc['pid']}, Name: {proc['name']}, CPU: {proc['cpu_percent']}%")
```

### SystemResourceMonitor

Monitors and manages system resources.

#### Methods

##### `get_cpu_usage(self, per_cpu: bool = False) -> Union[float, Dict[int, float]]`
Get current CPU usage.

**Parameters**:
- `per_cpu` (bool, optional): If True, returns usage per CPU core. Defaults to False.

**Returns**:
- `Union[float, Dict[int, float]]`: CPU usage percentage(s).

**Example**:
```python
# Get overall CPU usage
cpu_usage = kadv.resource_monitor.get_cpu_usage()
print(f"CPU Usage: {cpu_usage}%")

# Get per-CPU usage
cpu_cores = kadv.resource_monitor.get_cpu_usage(per_cpu=True)
for core, usage in cpu_cores.items():
    print(f"Core {core}: {usage}%")
```

##### `get_memory_usage(self) -> Dict[str, Any]`
Get memory usage information.

**Returns**:
- `Dict[str, Any]`: Memory usage statistics.

**Example**:
```python
mem = kadv.resource_monitor.get_memory_usage()
print(f"Used: {mem['used']} MB")
print(f"Available: {mem['available']} MB")
print(f"Percentage: {mem['percent']}%")
```

### ProcessManager

Handles process execution and management.

#### Methods

##### `execute_command(self, command: Union[str, List[str]], **kwargs) -> Dict[str, Any]`
Execute a shell command.

**Parameters**:
- `command` (Union[str, List[str]]): Command to execute.
- `**kwargs`: Additional arguments (timeout, cwd, env, etc.).

**Returns**:
- `Dict[str, Any]`: Command execution result.

**Example**:
```python
# Simple command
result = kadv.process_manager.execute_command("ls -la")
print(f"Exit code: {result['returncode']}")
print(f"Output: {result['stdout']}")

# With options
result = kadv.process_manager.execute_command(
    ["python", "script.py"],
    cwd="/path/to/script",
    timeout=30,
    env={"PYTHONPATH": "/custom/path"}
)
```

##### `get_process(self, pid: int) -> Optional[Dict[str, Any]]`
Get information about a specific process.

**Parameters**:
- `pid` (int): Process ID.

**Returns**:
- `Optional[Dict[str, Any]]`: Process information or None if not found.

**Example**:
```python
process = kadv.process_manager.get_process(os.getpid())
if process:
    print(f"Process name: {process['name']}")
    print(f"Status: {process['status']}")
```

## Event System

KADVLayer provides an event-based system for monitoring system changes.

### Registering Event Handlers

```python
def on_cpu_usage_high(usage):
    print(f"High CPU usage detected: {usage}%")

# Register event handler
kadv.events.subscribe('cpu_high', on_cpu_usage_high)

# Trigger event manually (usually handled internally)
kadv.events.publish('cpu_high', 95)

# Unsubscribe
kadv.events.unsubscribe('cpu_high', on_cpu_usage_high)
```

### Available Events

- `cpu_high`: Triggered when CPU usage exceeds threshold
- `memory_low`: Triggered when available memory is low
- `process_started`: When a new process starts
- `process_ended`: When a process ends
- `disk_usage_high`: When disk usage exceeds threshold
- `network_usage_high`: When network usage exceeds threshold

## Error Handling

KADVLayer raises specific exceptions for different error conditions:

- `SystemNotSupportedError`: Feature not available on current system
- `PermissionError`: Insufficient permissions
- `ProcessNotFound`: Process not found
- `CommandExecutionError`: Command execution failed

**Example**:
```python
try:
    kadv.start_monitoring()
except PermissionError as e:
    print(f"Permission denied: {e}")
    # Handle error
```

## Best Practices

1. **Resource Cleanup**: Always call `stop_monitoring()` when done
2. **Error Handling**: Handle exceptions appropriately
3. **Performance**: Be mindful of monitoring frequency
4. **Thread Safety**: KADVLayer is thread-safe, but be careful with shared state
5. **Event Handling**: Keep event handlers short and non-blocking

## Example: System Monitor

```python
from kos.advanced import KADVLayer
import time

def on_high_cpu(usage):
    print(f"Alert: High CPU usage detected: {usage}%")

def on_low_memory(available_mb):
    print(f"Alert: Low memory available: {available_mb} MB")

def main():
    kadv = KADVLayer({
        "monitoring_interval": 2.0,
        "cpu_threshold": 80.0,
        "memory_threshold": 1024  # MB
    })
    
    # Register event handlers
    kadv.events.subscribe('cpu_high', on_high_cpu)
    kadv.events.subscribe('memory_low', on_low_memory)
    
    try:
        print("Starting system monitoring...")
        kadv.start_monitoring()
        
        # Keep the program running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping monitoring...")
    finally:
        kadv.stop_monitoring()
        print("Monitoring stopped.")

if __name__ == "__main__":
    main()
```

## See Also

- [Package Manager API](./package-manager.md)
- [Shell Integration](./shell-integration.md)
- [System Monitoring Guide](../guides/system-monitoring.md)

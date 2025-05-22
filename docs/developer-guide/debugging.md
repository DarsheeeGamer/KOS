# Debugging in KOS

This guide provides comprehensive debugging techniques and tools for KOS development.

## Table of Contents
- [Debugging Tools](#debugging-tools)
- [Logging](#logging)
- [Interactive Debugging](#interactive-debugging)
- [Performance Profiling](#performance-profiling)
- [Memory Analysis](#memory-analysis)
- [Network Debugging](#network-debugging)
- [Common Issues](#common-issues)
- [Best Practices](#best-practices)

## Debugging Tools

### Built-in Python Debugger (pdb)
```python
# Add breakpoint in code
import pdb; pdb.set_trace()

# Or use breakpoint() in Python 3.7+
breakpoint()
```

### Common pdb Commands
```
(Pdb) h              # Help
(Pdb) n              # Next line
(Pdb) s              # Step into function
(Pdb) c              # Continue until next breakpoint
(Pdb) p variable     # Print variable
(Pdb) l              # List source code
(Pdb) w              # Print stack trace
(Pdb) q              # Quit debugger
```

### IPython Debugger (ipdb)
```bash
# Install ipdb
$ pip install ipdb

# Usage
import ipdb; ipdb.set_trace()
```

## Logging

### Basic Logging
```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='kos_debug.log'
)

logger = logging.getLogger(__name__)


# Log messages
logger.debug('Debug message')
logger.info('Info message')
logger.warning('Warning message')
logger.error('Error message')
logger.critical('Critical message')
```

### Logging Configuration
```python
# config/logging.conf
[loggers]
keys=root,kos

[handlers]
keys=consoleHandler,fileHandler

[formatters]
keys=simpleFormatter

[logger_root]
level=DEBUG
handlers=consoleHandler

[logger_kos]
level=DEBUG
handlers=consoleHandler,fileHandler
qualname=kos
propagate=0

[handler_consoleHandler]
class=StreamHandler
level=DEBUG
formatter=simpleFormatter
args=(sys.stdout,)

[handler_fileHandler]
class=FileHandler
level=DEBUG
formatter=simpleFormatter
args=('kos_debug.log', 'a')

[formatter_simpleFormatter]
format=%(asctime)s - %(name)s - %(levelname)s - %(message)s
datefmt=%Y-%m-%d %H:%M:%S
```

## Interactive Debugging

### Debugging with VSCode
1. Add breakpoints by clicking left of line numbers
2. Press F5 to start debugging
3. Use debug toolbar to step through code

### Debugging with PyCharm
1. Right-click and select 'Debug'
2. Use the debug console to inspect variables
3. Set conditional breakpoints

## Performance Profiling

### cProfile
```bash
# Profile a script
$ python -m cProfile -o output.pstats your_script.py

# Generate report
$ gprof2dot -f pstats output.pstats | dot -Tpng -o output.png
```

### line_profiler
```python
# Install
$ pip install line_profiler

# Add decorator to function
@profile
def slow_function():
    # Function code
    pass

# Run profiler
$ kernprof -l -v script.py
```

## Memory Analysis

### memory_profiler
```python
# Install
$ pip install memory_profiler

# Add decorator
@profile
def memory_intensive_function():
    # Function code
    pass

# Run with memory profiler
$ python -m memory_profiler script.py
```

### objgraph
```python
# Install
$ pip install objgraph

# Find memory leaks
import objgraph
objgraph.show_most_common_types(limit=10)

# Show reference chain
objgraph.show_backref([object], max_depth=10)
```

## Network Debugging

### HTTP Requests
```python
import http.client

# Enable debug logging
http.client.HTTPConnection.debuglevel = 1

# Or for requests
import logging
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True
```

### Network Analysis
```bash
# Check open ports
$ netstat -tuln
$ ss -tuln

# Monitor network traffic
$ tcpdump -i any port 80 -w output.pcap
$ wireshark output.pcap
```

## Common Issues

### Import Errors
```python
# Check Python path
import sys
print(sys.path)

# Add to path
sys.path.append('/path/to/module')
```

### Database Issues
```python
# Enable SQL logging
import logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

### Threading Issues
```python
# Dump all threads
import sys, traceback
for thread_id, frame in sys._current_frames().items():
    print(f"Thread {thread_id}:")
    traceback.print_stack(frame)
```

## Best Practices

### Debugging Workflow
1. Reproduce the issue
2. Gather information (logs, stack traces)
3. Form a hypothesis
4. Test the hypothesis
5. Fix the issue
6. Add tests to prevent regression

### Logging Best Practices
1. Use appropriate log levels
2. Include contextual information
3. Use structured logging
4. Rotate log files
5. Don't log sensitive information

### Performance Tips
1. Profile before optimizing
2. Focus on the bottleneck
3. Use appropriate data structures
4. Cache expensive operations
5. Use generators for large datasets

## See Also
- [Testing Guide](./testing.md)
- [Developer Guide](../developer-guide/README.md)
- [Performance Optimization](./performance-optimization.md)

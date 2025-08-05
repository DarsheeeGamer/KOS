# KOS Device Driver Framework

A complete device driver framework for the KOS (Kaede Operating System) with C/C++ implementation and Python bindings.

## Overview

This framework provides a comprehensive device driver infrastructure that supports:

- **Character devices** - Stream-oriented devices (terminals, pipes, etc.)
- **Block devices** - Block-oriented storage devices (disks, partitions, etc.)
- **Network devices** - Network interface devices (ethernet, wifi, etc.)
- **TTY devices** - Terminal devices with line discipline and signal handling

## Architecture

### Core Components

1. **Base Driver Infrastructure** (`base.c`)
   - Device registration and management
   - Driver lifecycle management
   - Memory management (DMA support)
   - Interrupt handling
   - Reference counting

2. **Character Device Driver** (`char.c`)
   - Stream-based I/O operations
   - Buffering and flow control
   - Non-blocking I/O support
   - IOCTL interface

3. **Block Device Driver** (`block.c`)
   - Block-based I/O operations
   - Caching system (write-through)
   - Geometry management
   - Performance statistics

4. **Network Device Driver** (`net.c`)
   - Packet send/receive operations
   - MAC address management
   - MTU configuration
   - Network statistics
   - Interface up/down control

5. **TTY Device Driver** (`tty.c`)
   - Terminal line discipline
   - Canonical and raw modes
   - Echo and signal processing
   - Window size management
   - Process group handling

6. **Python Bindings** (`drivers_wrapper.py`)
   - Complete Python API
   - Object-oriented interface
   - Thread-safe operations
   - Error handling

## File Structure

```
kos/kernel/drivers/
├── drivers.h              # Main header file with all definitions
├── base.c                 # Base driver infrastructure
├── char.c                 # Character device implementation
├── block.c                # Block device implementation  
├── net.c                  # Network device implementation
├── tty.c                  # TTY device implementation
├── drivers_wrapper.py     # Python bindings
├── Makefile              # Build system
├── test_drivers.py       # Comprehensive test suite
├── example_usage.py      # Usage examples
├── test_simple.py        # Simple functionality test
└── README.md             # This file
```

## Features

### Device Management
- Device registration/unregistration
- Reference counting
- Thread-safe operations
- Device discovery and enumeration

### I/O Operations
- Synchronous and asynchronous I/O
- Blocking and non-blocking modes
- Buffer management
- Error handling

### Memory Management
- DMA descriptor allocation
- Memory mapping support
- Aligned memory allocation
- Automatic cleanup

### Interrupt Handling
- IRQ request/release
- Handler registration
- Enable/disable control
- Thread-safe interrupt management

### IOCTL Interface
- Device-specific controls
- Configuration management
- Status queries
- Performance monitoring

## Building

### Prerequisites
- GCC compiler
- pthread library
- Standard C library
- Python 3.6+ (for bindings)

### Compilation
```bash
make clean
make
```

This will produce `libkos_drivers.so` shared library.

### Installation
```bash
make install
```

This installs the library and headers system-wide.

## Usage

### C/C++ API

```c
#include "drivers.h"

// Initialize the driver subsystem
kos_device_init();

// Create a character device
kos_char_device_create("console", NULL, NULL);

// Find and use the device
kos_device_t *dev = kos_device_find("console");
if (dev && dev->fops && dev->fops->write) {
    dev->fops->write(dev, "Hello, World!", 13, 0);
}

// Cleanup
kos_device_cleanup();
```

### Python API

```python
import drivers_wrapper as kos

# Create devices
char_dev = kos.create_char_device("console")
block_dev = kos.create_block_device("disk0", 1024*1024, 512)
net_dev = kos.create_network_device("eth0")
tty_dev = kos.create_tty_device("tty0")

# Use character device
char_dev.write(b"Hello, World!")
data = char_dev.read()

# Use block device
block_data = b"A" * 512
block_dev.write_block(0, block_data)
read_block = block_dev.read_block(0)

# Use network device
net_dev.up()
net_dev.send_packet(b"Network packet")
received = net_dev.receive_packet()

# Use TTY device
tty_dev.input_char('H')
tty_dev.input_char('i')
tty_dev.input_char('\n')
line = tty_dev.read_line()

# Cleanup
kos.destroy_device("console")
kos.destroy_device("disk0")
kos.destroy_device("eth0")
kos.destroy_device("tty0")
```

## Device Types

### Character Devices
- Stream-oriented I/O
- Variable-length data
- Examples: terminals, pipes, serial ports

**Key Operations:**
- `read()` - Read data stream
- `write()` - Write data stream  
- `ioctl()` - Device control
- `flush()` - Flush buffers

### Block Devices
- Fixed-size block I/O
- Random access
- Examples: hard drives, SSDs, RAM disks

**Key Operations:**
- `read_block()` - Read single block
- `write_block()` - Write single block
- `read_blocks()` - Read multiple blocks
- `write_blocks()` - Write multiple blocks
- `get_geometry()` - Get device geometry

### Network Devices
- Packet-based I/O
- Network protocol support
- Examples: Ethernet, WiFi, loopback

**Key Operations:**
- `send_packet()` - Send network packet
- `receive_packet()` - Receive network packet
- `up()` - Bring interface up
- `down()` - Bring interface down
- `set_mac_addr()` - Set MAC address
- `set_mtu()` - Set MTU size

### TTY Devices
- Terminal line discipline
- Character processing
- Examples: console, pseudo-terminals

**Key Operations:**
- `input_char()` - Process input character
- `read_line()` - Read complete line
- `write()` - Output text
- `set_raw_mode()` - Set raw mode
- `set_cooked_mode()` - Set canonical mode

## Testing

### Comprehensive Test Suite
```bash
python3 test_drivers.py
```

Runs extensive tests including:
- All device types
- Error handling
- Multi-threading
- Performance benchmarks
- Stress testing

### Simple Functionality Test
```bash
python3 test_simple.py
```

Quick verification of basic functionality.

### Usage Examples
```bash
python3 example_usage.py
```

Demonstrates real-world usage scenarios:
- Virtual disk simulation
- Network packet processing
- Terminal emulation
- Log file system
- Multi-threaded access

## Error Handling

The framework provides comprehensive error handling:

### Error Codes
- `KOS_ERR_SUCCESS` - Operation successful
- `KOS_ERR_INVALID_PARAM` - Invalid parameter
- `KOS_ERR_NO_MEMORY` - Out of memory
- `KOS_ERR_DEVICE_BUSY` - Device busy
- `KOS_ERR_NOT_SUPPORTED` - Operation not supported
- `KOS_ERR_IO_ERROR` - I/O error
- `KOS_ERR_TIMEOUT` - Operation timed out

### Python Exceptions
- `KOSDriverError` - Base exception
- `DeviceNotFoundError` - Device not found
- `DeviceBusyError` - Device busy
- `InvalidParameterError` - Invalid parameter

## Thread Safety

All operations are thread-safe:
- Device management uses mutexes
- I/O operations are atomic
- Reference counting prevents race conditions
- Interrupt handling is serialized

## Performance Features

### Caching
- Block device write-through cache
- LRU replacement policy
- Configurable cache size

### Statistics
- I/O operation counters
- Data transfer metrics
- Performance monitoring
- Error tracking

### Optimizations
- Aligned memory allocation
- Efficient buffer management
- Minimal locking overhead
- Zero-copy operations where possible

## Integration with KOS

This driver framework integrates seamlessly with the KOS operating system:

- **Kernel Integration** - Direct kernel API access
- **System Calls** - Maps to KOS system call interface
- **Process Management** - Works with KOS process model
- **Memory Management** - Uses KOS memory allocator
- **Interrupt Handling** - Integrates with KOS interrupt system

## Future Enhancements

Planned improvements include:
- DMA engine integration
- Hot-plug device support
- Power management
- Device driver modules
- Performance profiling
- Hardware abstraction layer

## License

This code is part of the KOS (Kaede Operating System) project.

## Contributing

When contributing to this driver framework:
1. Follow the existing code style
2. Add comprehensive tests
3. Update documentation
4. Ensure thread safety
5. Test on multiple platforms

## API Reference

See `drivers.h` for the complete C API reference and `drivers_wrapper.py` for the Python API documentation.
#!/usr/bin/env python3
"""
KOS Core Components Test Script

This script demonstrates and tests the core components of KOS:
- Hardware Abstraction Layer (HAL)
- Process Management
- Memory Management
- Filesystem
"""

import os
import sys
import time
import logging
from typing import Dict, Any

# Add the parent directory to the Python path to import KOS modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import KOS core components
from kos.core import initialize_core, get_core_status, shutdown_core
import kos.core.hal as hal
import kos.core.process as process
import kos.core.memory as memory
import kos.core.filesystem as filesystem
from kos.core.filesystem import FileSystemType, FileType

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('KOS.test')


def print_section(title):
    """Print a section title"""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def test_hal():
    """Test Hardware Abstraction Layer"""
    print_section("Testing Hardware Abstraction Layer (HAL)")
    
    # Get hardware information
    print("\nHardware Information:")
    hw_info = hal.get_hardware_info()
    
    # System info
    if 'system' in hw_info:
        print("\n  System Information:")
        for key, value in hw_info['system'].items():
            print(f"    {key}: {value}")
    
    # CPU info
    if 'cpu' in hw_info:
        print("\n  CPU Information:")
        for key, value in hw_info['cpu'].items():
            print(f"    {key}: {value}")
    
    # Memory info
    if 'memory' in hw_info:
        print("\n  Memory Information:")
        for key, value in hw_info['memory'].items():
            if isinstance(value, dict):
                print(f"    {key}:")
                for k, v in value.items():
                    print(f"      {k}: {format_bytes(v) if 'total' in k or 'available' in k else v}")
            else:
                print(f"    {key}: {value}")
    
    # List devices
    print("\nDetected Devices:")
    devices = hal.list_devices()
    
    for device in devices:
        print(f"\n  {device.name} ({device.device_id}):")
        print(f"    Type: {device.device_type}")
        print(f"    Description: {device.description}")
        
        # Get device status if driver is available
        driver = hal.get_driver(device.device_id)
        if driver:
            status = driver.get_status()
            print(f"    Status: {status.get('initialized', False)}")
            
            # Show device-specific status information
            if device.device_type == hal.DeviceType.CPU and 'percent' in status:
                print(f"    CPU Usage: {status['percent']}%")
            elif device.device_type == hal.DeviceType.MEMORY and 'virtual' in status:
                print(f"    Memory Usage: {status['virtual']['percent']}%")
                print(f"    Total Memory: {format_bytes(status['virtual']['total'])}")
                print(f"    Available Memory: {format_bytes(status['virtual']['available'])}")
            elif device.device_type == hal.DeviceType.STORAGE and 'usage' in status:
                print(f"    Storage Usage: {status['usage']['percent']}%")
                print(f"    Total Storage: {format_bytes(status['usage']['total'])}")
                print(f"    Free Storage: {format_bytes(status['usage']['free'])}")


def test_process_management():
    """Test Process Management"""
    print_section("Testing Process Management")
    
    # Create a simple process
    print("\nCreating processes:")
    
    # Create a system process
    system_pid = process.create_process(
        name="system_test",
        command=None,  # System process
        priority=process.ProcessPriority.HIGH
    )
    
    print(f"  Created system process: PID {system_pid}")
    
    # Create an external process
    # On Windows, use 'cmd.exe /c dir'
    # On Linux, use '/bin/ls'
    command = 'cmd.exe' if sys.platform == 'win32' else '/bin/ls'
    args = ['/c', 'dir'] if sys.platform == 'win32' else ['-la']
    
    external_pid = process.create_process(
        name="external_test",
        command=command,
        args=args,
        parent_pid=system_pid
    )
    
    print(f"  Created external process: PID {external_pid}")
    
    # Wait for the external process to complete
    print("\nWaiting for external process to complete...")
    time.sleep(1)
    
    # Get process status
    print("\nProcess Status:")
    
    system_status = process.get_process_status(system_pid)
    print(f"\n  System Process (PID {system_pid}):")
    print(f"    Name: {system_status['name']}")
    print(f"    State: {system_status['state']}")
    print(f"    Priority: {system_status['priority']}")
    print(f"    Runtime: {system_status['runtime']:.2f} seconds")
    print(f"    Children: {system_status['children']}")
    
    external_status = process.get_process_status(external_pid)
    print(f"\n  External Process (PID {external_pid}):")
    print(f"    Name: {external_status['name']}")
    print(f"    State: {external_status['state']}")
    print(f"    Command: {external_status['command']}")
    print(f"    Args: {external_status['args']}")
    print(f"    Exit Code: {external_status['exit_code']}")
    print(f"    Runtime: {external_status['runtime']:.2f} seconds")
    
    # List all processes
    print("\nAll Processes:")
    all_processes = process.get_all_processes()
    
    for pid, proc in all_processes.items():
        status = proc.get_status()
        print(f"  PID {pid}: {status['name']} ({status['state']})")
    
    # Terminate the system process
    print("\nTerminating system process...")
    process.terminate_process(system_pid)
    
    time.sleep(0.5)
    
    # Verify termination
    system_status = process.get_process_status(system_pid)
    print(f"  System process state: {system_status['state']}")


def test_memory_management():
    """Test Memory Management"""
    print_section("Testing Memory Management")
    
    # Get memory information
    print("\nMemory Information:")
    mem_info = memory.get_memory_info()
    
    print(f"  Total Memory: {format_bytes(mem_info['total_memory'])}")
    print(f"  Available Memory: {format_bytes(mem_info['available_memory'])}")
    print(f"  Allocated Memory: {format_bytes(mem_info['allocated_memory'])}")
    print(f"  Page Size: {format_bytes(mem_info['page_size'])}")
    print(f"  Fragmentation: {mem_info['fragmentation']}%")
    
    # Allocate memory
    print("\nAllocating Memory:")
    
    # Allocate a 1MB block
    addr1 = memory.allocate_memory(
        size=1024 * 1024,
        mem_type=memory.MemoryType.USER,
        permissions=memory.MemoryPermission.READ_WRITE,
        name="test_block_1"
    )
    
    print(f"  Allocated 1MB at address: 0x{addr1:x}")
    
    # Allocate a 512KB block
    addr2 = memory.allocate_memory(
        size=512 * 1024,
        mem_type=memory.MemoryType.USER,
        permissions=memory.MemoryPermission.READ_WRITE,
        name="test_block_2"
    )
    
    print(f"  Allocated 512KB at address: 0x{addr2:x}")
    
    # Get memory block information
    print("\nMemory Block Information:")
    
    block1_info = memory.get_memory_info(addr1)
    print(f"\n  Block 1 (0x{addr1:x}):")
    print(f"    Name: {block1_info['name']}")
    print(f"    Size: {format_bytes(block1_info['size'])}")
    print(f"    Type: {block1_info['type']}")
    print(f"    Permissions: {block1_info['permissions']}")
    
    block2_info = memory.get_memory_info(addr2)
    print(f"\n  Block 2 (0x{addr2:x}):")
    print(f"    Name: {block2_info['name']}")
    print(f"    Size: {format_bytes(block2_info['size'])}")
    print(f"    Type: {block2_info['type']}")
    print(f"    Permissions: {block2_info['permissions']}")
    
    # Write and read memory
    print("\nMemory Read/Write Test:")
    
    # Write data to block 1
    test_data = b"Hello, KOS Memory Management!"
    memory.write_memory(addr1, test_data)
    
    # Read data back
    read_data = memory.read_memory(addr1, len(test_data))
    
    print(f"  Wrote: {test_data}")
    print(f"  Read: {read_data}")
    print(f"  Match: {test_data == read_data}")
    
    # Free memory
    print("\nFreeing Memory:")
    
    memory.free_memory(addr1)
    print(f"  Freed block at 0x{addr1:x}")
    
    memory.free_memory(addr2)
    print(f"  Freed block at 0x{addr2:x}")
    
    # Get updated memory information
    mem_info = memory.get_memory_info()
    print(f"\n  Available Memory: {format_bytes(mem_info['available_memory'])}")
    print(f"  Allocated Memory: {format_bytes(mem_info['allocated_memory'])}")


def test_filesystem():
    """Test Filesystem"""
    print_section("Testing Filesystem")
    
    # Get mounted filesystems
    print("\nMounted Filesystems:")
    
    mounted_fs = filesystem.get_mounted_filesystems()
    
    for mount_point, fs_info in mounted_fs.items():
        print(f"  {mount_point}: {fs_info['type']} ({fs_info['name']})")
    
    # Mount a memory filesystem
    print("\nMounting a new memory filesystem:")
    
    mount_point = "/mnt/test"
    success = filesystem.mount(FileSystemType.MEMORY, mount_point, "test_fs")
    
    print(f"  Mount result: {'Success' if success else 'Failed'}")
    
    # Create some directories and files
    print("\nCreating directories and files:")
    
    # Create a directory
    filesystem.create_directory(f"{mount_point}/testdir")
    print(f"  Created directory: {mount_point}/testdir")
    
    # Create nested directories
    filesystem.create_directory(f"{mount_point}/testdir/nested/deep", cwd=mount_point)
    print(f"  Created nested directories: {mount_point}/testdir/nested/deep")
    
    # Create a file
    test_content = b"Hello, KOS Filesystem!"
    filesystem.write_entire_file(f"{mount_point}/testfile.txt", test_content)
    print(f"  Created file: {mount_point}/testfile.txt")
    
    # Create a file in a subdirectory
    nested_content = b"This is a nested file."
    filesystem.write_entire_file(f"{mount_point}/testdir/nested.txt", nested_content)
    print(f"  Created file: {mount_point}/testdir/nested.txt")
    
    # List directory contents
    print("\nDirectory Listing:")
    
    root_contents = filesystem.list_directory(mount_point)
    print(f"\n  {mount_point}/")
    for item in root_contents:
        print(f"    {item.name} ({item.type.value}, {format_bytes(item.size)})")
    
    subdir_contents = filesystem.list_directory(f"{mount_point}/testdir")
    print(f"\n  {mount_point}/testdir/")
    for item in subdir_contents:
        print(f"    {item.name} ({item.type.value}, {format_bytes(item.size)})")
    
    # Read a file
    print("\nReading files:")
    
    read_content = filesystem.read_entire_file(f"{mount_point}/testfile.txt")
    print(f"  {mount_point}/testfile.txt: {read_content}")
    
    read_nested = filesystem.read_entire_file(f"{mount_point}/testdir/nested.txt")
    print(f"  {mount_point}/testdir/nested.txt: {read_nested}")
    
    # Get file information
    print("\nFile Information:")
    
    file_info = filesystem.get_file_info(f"{mount_point}/testfile.txt")
    print(f"\n  {mount_point}/testfile.txt:")
    print(f"    Type: {file_info.type.value}")
    print(f"    Size: {format_bytes(file_info.size)}")
    print(f"    Created: {format_time(file_info.created)}")
    print(f"    Modified: {format_time(file_info.modified)}")
    print(f"    Permissions: {file_info.permissions:o}")
    
    # Copy, move, and delete operations
    print("\nFile Operations:")
    
    # Copy a file
    filesystem.copy_file(f"{mount_point}/testfile.txt", f"{mount_point}/testfile_copy.txt")
    print(f"  Copied {mount_point}/testfile.txt to {mount_point}/testfile_copy.txt")
    
    # Rename/move a file
    filesystem.move_file(f"{mount_point}/testfile_copy.txt", f"{mount_point}/testdir/moved.txt")
    print(f"  Moved {mount_point}/testfile_copy.txt to {mount_point}/testdir/moved.txt")
    
    # Delete a file
    filesystem.delete_file(f"{mount_point}/testfile.txt")
    print(f"  Deleted {mount_point}/testfile.txt")
    
    # Verify the results
    print("\nUpdated Directory Listing:")
    
    root_contents = filesystem.list_directory(mount_point)
    print(f"\n  {mount_point}/")
    for item in root_contents:
        print(f"    {item.name} ({item.type.value}, {format_bytes(item.size)})")
    
    subdir_contents = filesystem.list_directory(f"{mount_point}/testdir")
    print(f"\n  {mount_point}/testdir/")
    for item in subdir_contents:
        print(f"    {item.name} ({item.type.value}, {format_bytes(item.size)})")
    
    # Unmount the filesystem
    print("\nUnmounting filesystem:")
    
    success = filesystem.unmount(mount_point)
    print(f"  Unmount result: {'Success' if success else 'Failed'}")


def test_integration():
    """Test integration between components"""
    print_section("Testing Component Integration")
    
    # 1. Create a filesystem
    print("\nCreating a memory filesystem for testing")
    mount_point = "/mnt/integration"
    filesystem.mount(FileSystemType.MEMORY, mount_point, "integration_fs")
    
    # 2. Create a test file with data from memory
    print("\nAllocating memory for file data")
    addr = memory.allocate_memory(
        size=1024,
        mem_type=memory.MemoryType.USER,
        permissions=memory.MemoryPermission.READ_WRITE,
        name="file_data"
    )
    
    # Write test data to memory
    test_data = b"This data travels from memory to filesystem via process!"
    memory.write_memory(addr, test_data)
    
    # Read it back from memory
    mem_data = memory.read_memory(addr, len(test_data))
    
    # 3. Create a process to handle the data transfer
    print("\nCreating a process to handle data transfer")
    
    # This is a simulated process since we don't have a real executable
    data_pid = process.create_process(
        name="data_transfer",
        command=None  # System process
    )
    
    # 4. Use the process to write the data to a file
    print("\nWriting memory data to filesystem")
    file_path = f"{mount_point}/memory_data.txt"
    filesystem.write_entire_file(file_path, mem_data)
    
    # 5. Read the file back
    print("\nReading data back from filesystem")
    file_data = filesystem.read_entire_file(file_path)
    
    # 6. Verify the data
    print("\nVerifying data integrity")
    print(f"  Original data: {test_data}")
    print(f"  Memory data: {mem_data}")
    print(f"  File data: {file_data}")
    print(f"  Data integrity: {'Maintained' if test_data == file_data else 'Lost'}")
    
    # 7. Clean up
    print("\nCleaning up resources")
    memory.free_memory(addr)
    process.terminate_process(data_pid)
    filesystem.delete_file(file_path)
    filesystem.unmount(mount_point)
    
    print("\nComponent integration test complete")


def format_bytes(size):
    """Format bytes to human-readable format"""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.1f} GB"


def format_time(timestamp):
    """Format timestamp to human-readable format"""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))


def main():
    """Main function"""
    print("\nKOS Core Components Test")
    print("=======================\n")
    
    print("Initializing KOS core components...")
    success = initialize_core()
    
    if not success:
        print("Failed to initialize KOS core components. Exiting.")
        return
    
    print("Core components initialized successfully!\n")
    
    # Run the tests
    try:
        test_hal()
        test_process_management()
        test_memory_management()
        test_filesystem()
        test_integration()
    
    except Exception as e:
        print(f"\nError during testing: {e}")
    
    finally:
        # Shutdown core components
        print("\nShutting down KOS core components...")
        shutdown_core()
        print("Core components shutdown complete.")


if __name__ == "__main__":
    main()

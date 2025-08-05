#!/usr/bin/env python3
"""
KOS Device Driver Framework Usage Examples

This script demonstrates practical usage of the KOS device driver framework
with real-world scenarios and use cases.
"""

import os
import sys
import time
import threading
from typing import Optional

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drivers_wrapper import (
    create_char_device,
    create_block_device,
    create_network_device,
    create_tty_device,
    destroy_device,
    list_devices,
    IOCTLCommands
)

def example_virtual_disk():
    """Example: Create and use a virtual disk drive"""
    print("=== Virtual Disk Example ===")
    
    # Create a 10MB virtual disk with 4KB blocks
    disk = create_block_device("virtual_disk", 10 * 1024 * 1024, 4096)
    print(f"Created virtual disk: {disk.name}")
    print(f"  Size: {disk.size:,} bytes ({disk.size // (1024*1024)} MB)")
    print(f"  Block size: {disk.block_size:,} bytes")
    print(f"  Total blocks: {disk.total_blocks:,}")
    
    # Write a "file system" header
    header = b"KOS Virtual Disk v1.0\x00" + b"\x00" * (disk.block_size - 22)
    disk.write_block(0, header)
    print("  Wrote file system header to block 0")
    
    # Create some "files" by writing to different blocks
    files = {
        "readme.txt": b"Welcome to KOS virtual disk!\nThis is a simulated file system.",
        "config.json": b'{"name": "virtual_disk", "version": "1.0", "blocks": ' + str(disk.total_blocks).encode() + b'}',
        "data.bin": bytes(range(256)) * 16  # 4KB of binary data
    }
    
    block_num = 1
    file_table = {}
    
    for filename, content in files.items():
        # Pad content to block size
        padded_content = content + b"\x00" * (disk.block_size - len(content))
        disk.write_block(block_num, padded_content)
        file_table[filename] = block_num
        print(f"  Wrote {filename} to block {block_num} ({len(content)} bytes)")
        block_num += 1
    
    # Read back and verify files
    print("\n  Verifying files:")
    for filename, block in file_table.items():
        data = disk.read_block(block)
        original_size = len(files[filename])
        retrieved = data[:original_size]
        if retrieved == files[filename]:
            print(f"    ✓ {filename} verified")
        else:
            print(f"    ✗ {filename} verification failed")
    
    # Show disk statistics
    info = disk.get_info()
    print(f"\n  Disk statistics:")
    print(f"    Read operations: {info.read_count}")
    print(f"    Write operations: {info.write_count}")
    print(f"    Bytes read: {info.read_bytes:,}")
    print(f"    Bytes written: {info.write_bytes:,}")
    
    # Cleanup
    destroy_device("virtual_disk")
    print("  Virtual disk destroyed")

def example_network_simulation():
    """Example: Network packet processing simulation"""
    print("\n=== Network Simulation Example ===")
    
    # Create two network interfaces
    eth0 = create_network_device("eth0", b"\x02\x00\x00\x00\x00\x01")
    eth1 = create_network_device("eth1", b"\x02\x00\x00\x00\x00\x02")
    
    print(f"Created network interfaces:")
    print(f"  {eth0.name}: MAC {eth0.mac_addr.hex(':').upper()}")
    print(f"  {eth1.name}: MAC {eth1.mac_addr.hex(':').upper()}")
    
    # Bring interfaces up
    eth0.up()
    eth1.up()
    print("  Interfaces brought up")
    
    # Simulate network traffic
    packets = [
        b"\x02\x00\x00\x00\x00\x02\x02\x00\x00\x00\x00\x01\x08\x00Hello from eth0!",
        b"\x02\x00\x00\x00\x00\x01\x02\x00\x00\x00\x00\x02\x08\x00Hello from eth1!",
        b"\x02\x00\x00\x00\x00\x02\x02\x00\x00\x00\x00\x01\x08\x00Ping packet",
        b"\x02\x00\x00\x00\x00\x01\x02\x00\x00\x00\x00\x02\x08\x00Pong packet",
    ]
    
    print("\n  Simulating network traffic:")
    
    # Send packets from eth0 to eth1
    for i, packet in enumerate(packets[:2]):
        eth0.send_packet(packet)
        # Simulate packet reaching eth1
        eth1.inject_packet(packet)
        print(f"    Packet {i+1} sent from {eth0.name} to {eth1.name}")
    
    # Send packets from eth1 to eth0
    for i, packet in enumerate(packets[2:], 3):
        eth1.send_packet(packet)
        # Simulate packet reaching eth0
        eth0.inject_packet(packet)
        print(f"    Packet {i} sent from {eth1.name} to {eth0.name}")
    
    # Process received packets
    print("\n  Processing received packets:")
    for interface in [eth0, eth1]:
        while True:
            packet = interface.receive_packet()
            if packet is None:
                break
            
            # Extract source and destination MAC addresses
            dst_mac = packet[:6].hex(':').upper()
            src_mac = packet[6:12].hex(':').upper()
            payload = packet[14:]  # Skip Ethernet header
            
            print(f"    {interface.name} received: {src_mac} -> {dst_mac}: {payload.decode('utf-8', errors='ignore')}")
    
    # Show network statistics
    print("\n  Network statistics:")
    for interface in [eth0, eth1]:
        stats = interface.get_stats()
        print(f"    {interface.name}:")
        print(f"      TX: {stats.tx_packets} packets, {stats.tx_bytes} bytes")
        print(f"      RX: {stats.rx_packets} packets, {stats.rx_bytes} bytes")
    
    # Test MTU configuration
    print("\n  Testing MTU configuration:")
    eth0.set_mtu(9000)  # Jumbo frames
    print(f"    {eth0.name} MTU set to {eth0.mtu}")
    
    # Cleanup
    destroy_device("eth0")
    destroy_device("eth1")
    print("  Network interfaces destroyed")

def example_terminal_emulation():
    """Example: Terminal emulation with TTY device"""
    print("\n=== Terminal Emulation Example ===")
    
    # Create a TTY device
    tty = create_tty_device("console")
    print(f"Created TTY device: {tty.name}")
    
    # Set up terminal
    tty.set_window_size(24, 80)
    print(f"  Terminal size: {tty.rows}x{tty.cols}")
    
    # Simulate user typing
    print("\n  Simulating user input:")
    commands = [
        "help",
        "ls -la",
        "echo Hello World",
        "cat /proc/version",
        "exit"
    ]
    
    for command in commands:
        print(f"    User types: {command}")
        
        # Input each character
        for char in command:
            tty.input_char(char)
        tty.input_char('\n')  # Press Enter
        
        # Read the complete line
        line = tty.read_line()
        print(f"    TTY received: {repr(line)}")
        
        # Simulate command execution and output
        if command == "help":
            tty.write("Available commands: help, ls, echo, cat, exit\n")
        elif command.startswith("ls"):
            tty.write("total 4\ndrwxr-xr-x 2 user user 4096 Jan 1 12:00 .\ndrwxr-xr-x 3 root root 4096 Jan 1 12:00 ..\n")
        elif command.startswith("echo"):
            message = command[5:]  # Remove "echo "
            tty.write(f"{message}\n")
        elif command.startswith("cat"):
            tty.write("KOS (Kaede Operating System) version 1.0\n")
        elif command == "exit":
            tty.write("Goodbye!\n")
        else:
            tty.write(f"Unknown command: {command}\n")
        
        # Show what would be displayed
        output = tty.read_output()
        if output:
            print(f"    Terminal output: {repr(output)}")
    
    # Test raw mode
    print("\n  Testing raw mode:")
    tty.set_raw_mode()
    print("    TTY set to raw mode")
    
    # In raw mode, characters are processed immediately
    raw_input = "CTRL-C"
    for char in raw_input:
        tty.input_char(char)
    
    # No echo in raw mode
    output = tty.read_output()
    print(f"    Raw mode output: {repr(output)}")
    
    # Get TTY information
    info = tty.get_info()
    print(f"\n  TTY statistics:")
    print(f"    Mode: {'Raw' if info.mode == 0 else 'Cooked'}")
    print(f"    Characters in: {info.chars_in}")
    print(f"    Characters out: {info.chars_out}")
    print(f"    Lines in: {info.lines_in}")
    print(f"    Lines out: {info.lines_out}")
    
    # Cleanup
    destroy_device("console")
    print("  TTY device destroyed")

def example_log_file_system():
    """Example: Simple log file system using character device"""
    print("\n=== Log File System Example ===")
    
    # Create a character device for logging
    log_device = create_char_device("system_log")
    print(f"Created log device: {log_device.name}")
    
    # Simulate system events
    events = [
        "System boot initiated",
        "Kernel modules loaded",
        "Device drivers initialized",
        "Network interfaces configured",
        "File systems mounted",
        "System ready"
    ]
    
    print("\n  Writing system events to log:")
    for i, event in enumerate(events, 1):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] EVENT {i:03d}: {event}\n"
        log_device.write(log_entry.encode())
        print(f"    Logged: {event}")
        time.sleep(0.1)  # Small delay for realistic timestamps
    
    # Read back the complete log
    print("\n  Reading complete log:")
    log_data = log_device.read()
    log_text = log_data.decode()
    
    print("    --- LOG START ---")
    print(log_text, end="")
    print("    --- LOG END ---")
    
    # Get device information
    info = log_device.ioctl(IOCTLCommands.GET_INFO)
    print(f"\n  Log device statistics:")
    print(f"    Buffer size: {info['buffer_size']} bytes")
    print(f"    Data available: {info['data_available']} bytes")
    
    # Cleanup
    destroy_device("system_log")
    print("  Log device destroyed")

def example_multi_threaded_access():
    """Example: Multi-threaded device access"""
    print("\n=== Multi-threaded Access Example ===")
    
    # Create a shared block device
    shared_disk = create_block_device("shared_disk", 64 * 1024, 512)
    print(f"Created shared disk: {shared_disk.name}")
    
    # Thread function for concurrent access
    def worker_thread(thread_id, device, num_operations):
        print(f"    Thread {thread_id} starting...")
        
        for i in range(num_operations):
            # Write thread-specific data
            data = f"Thread-{thread_id}-Op-{i:03d}".encode()
            data = data.ljust(device.block_size, b'\x00')  # Pad to block size
            
            block_num = (thread_id * num_operations + i) % device.total_blocks
            device.write_block(block_num, data)
            
            # Read it back to verify
            read_data = device.read_block(block_num)
            if read_data[:len(data.rstrip(b'\x00'))] != data.rstrip(b'\x00'):
                print(f"    Thread {thread_id}: Data verification failed!")
        
        print(f"    Thread {thread_id} completed {num_operations} operations")
    
    # Start multiple threads
    num_threads = 4
    num_ops_per_thread = 10
    threads = []
    
    print(f"\n  Starting {num_threads} threads with {num_ops_per_thread} operations each:")
    
    for i in range(num_threads):
        thread = threading.Thread(target=worker_thread, args=(i, shared_disk, num_ops_per_thread))
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # Verify final state
    info = shared_disk.get_info()
    expected_ops = num_threads * num_ops_per_thread
    
    print(f"\n  Multi-threaded access results:")
    print(f"    Expected operations: {expected_ops * 2}")  # Each thread does read+write
    print(f"    Actual read operations: {info.read_count}")
    print(f"    Actual write operations: {info.write_count}")
    print(f"    Total bytes transferred: {info.read_bytes + info.write_bytes:,}")
    
    # Cleanup
    destroy_device("shared_disk")
    print("  Shared disk destroyed")

def example_device_monitoring():
    """Example: Device monitoring and management"""
    print("\n=== Device Monitoring Example ===")
    
    # Create various devices
    devices_created = []
    
    print("  Creating monitoring devices:")
    devices_created.append(create_char_device("monitor_char"))
    devices_created.append(create_block_device("monitor_block", 1024 * 1024, 1024))
    devices_created.append(create_network_device("monitor_net"))
    devices_created.append(create_tty_device("monitor_tty"))
    
    for device in devices_created:
        print(f"    Created: {device.name} ({type(device).__name__})")
    
    # Monitor device activity
    print("\n  Generating device activity:")
    
    # Character device activity
    char_dev = devices_created[0]
    for i in range(5):
        char_dev.write(f"Monitor test {i}\n".encode())
    print(f"    {char_dev.name}: Wrote 5 messages")
    
    # Block device activity
    block_dev = devices_created[1]
    for i in range(3):
        data = f"Block {i} data".encode().ljust(block_dev.block_size, b'\x00')
        block_dev.write_block(i, data)
    print(f"    {block_dev.name}: Wrote 3 blocks")
    
    # Network device activity
    net_dev = devices_created[2]
    net_dev.up()
    for i in range(4):
        net_dev.send_packet(f"Network packet {i}".encode())
    print(f"    {net_dev.name}: Sent 4 packets")
    
    # TTY device activity
    tty_dev = devices_created[3]
    for char in "Hello TTY!\n":
        tty_dev.input_char(char)
    tty_dev.write("TTY response\n")
    print(f"    {tty_dev.name}: Processed input/output")
    
    # Generate device report
    print("\n  Device Activity Report:")
    print("  " + "=" * 50)
    
    for device in devices_created:
        print(f"    Device: {device.name} ({type(device).__name__})")
        
        try:
            if hasattr(device, 'get_info'):
                info = device.get_info()
                if hasattr(info, 'read_count'):  # Block device
                    print(f"      Operations: {info.read_count} reads, {info.write_count} writes")
                    print(f"      Data: {info.read_bytes:,} bytes read, {info.write_bytes:,} bytes written")
                elif hasattr(info, 'tx_packets'):  # Network device
                    print(f"      Packets: {info.stats.tx_packets} sent, {info.stats.rx_packets} received")
                    print(f"      Data: {info.stats.tx_bytes} bytes sent, {info.stats.rx_bytes} bytes received")
                    print(f"      Status: {'UP' if info.is_up else 'DOWN'}")
                elif hasattr(info, 'chars_in'):  # TTY device
                    print(f"      Characters: {info.chars_in} in, {info.chars_out} out")
                    print(f"      Lines: {info.lines_in} in, {info.lines_out} out")
                    print(f"      Mode: {'Canonical' if info.canonical else 'Raw'}")
            else:
                # Character device
                info = device.ioctl(IOCTLCommands.GET_INFO)
                print(f"      Buffer: {info['data_available']} bytes available")
        except Exception as e:
            print(f"      Error getting info: {e}")
    
    # List all devices in system
    all_devices = list_devices()
    print(f"\n  Total devices in system: {len(all_devices)}")
    for device_name in all_devices:
        print(f"    - {device_name}")
    
    # Cleanup all monitoring devices
    print("\n  Cleaning up monitoring devices:")
    for device in devices_created:
        destroy_device(device.name)
        print(f"    Destroyed: {device.name}")

def main():
    """Main example runner"""
    print("KOS Device Driver Framework Usage Examples")
    print("=" * 60)
    
    try:
        # Run all examples
        example_virtual_disk()
        example_network_simulation()
        example_terminal_emulation()
        example_log_file_system()
        example_multi_threaded_access()
        example_device_monitoring()
        
        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        
        # Final cleanup check
        remaining_devices = list_devices()
        if remaining_devices:
            print(f"\nWarning: {len(remaining_devices)} devices still active:")
            for device_name in remaining_devices:
                print(f"  - {device_name}")
                destroy_device(device_name)
            print("Cleaned up remaining devices.")
        else:
            print("\nAll devices properly cleaned up.")
        
    except Exception as e:
        print(f"\nError during examples: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
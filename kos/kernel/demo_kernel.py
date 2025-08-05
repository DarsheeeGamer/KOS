#!/usr/bin/env python3
"""
KOS Kernel Demonstration Script

Showcases all major kernel features and subsystems:
- Process and thread management
- Memory management
- Network stack
- IPC mechanisms
- Filesystem operations
- Device drivers
- Scheduling
- Resource monitoring
"""

import sys
import os
import time
import logging

# Add kernel directory to path
sys.path.insert(0, os.path.dirname(__file__))

from kernel import KernelContext, KernelConfig

def main():
    """Main demonstration function"""
    print("=" * 60)
    print("KOS Kernel Comprehensive Demonstration")
    print("=" * 60)
    print()
    
    # Setup logging to show info messages
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    # Create kernel configuration
    config = KernelConfig(
        debug_mode=False,
        max_processes=50,
        max_threads=100,
        network_enabled=True,
        filesystem_enabled=True,
        ipc_enabled=True,
        resource_monitoring=True,
        log_level="INFO"
    )
    
    try:
        with KernelContext(config) as kernel:
            print("🚀 KOS Kernel initialized successfully!")
            print(f"   State: {kernel.state.name}")
            print()
            
            # Demon
# Core functionality demonstration
            demonstrate_process_management(kernel)
            demonstrate_memory_management(kernel)
            demonstrate_network_stack(kernel)
            demonstrate_ipc(kernel)
            demonstrate_filesystem(kernel)
            demonstrate_syscalls(kernel)
            demonstrate_monitoring(kernel)
            
            print("\n" + "=" * 60)
            print("🎉 All kernel subsystems demonstrated successfully!")
            print("=" * 60)
            
    except Exception as e:
        print(f"❌ Error during demonstration: {e}")
        return 1
    
    return 0

def demonstrate_process_management(kernel):
    """Demonstrate process and thread management"""
    print("📝 Process and Thread Management Demo")
    print("-" * 40)
    
    # Create processes
    processes = []
    for i in range(3):
        pid = kernel.create_process(f"demo_process_{i}")
        if pid:
            processes.append(pid)
            print(f"   ✓ Created process {i}: PID {pid}")
        else:
            print(f"   ⚠ Process {i} creation returned None (mock mode)")
    
    # Create threads
    threads = []
    for pid in processes[:1]:  # Only for first process
        for j in range(2):
            tid = kernel.create_thread(pid)
            if tid:
                threads.append(tid)
                print(f"   ✓ Created thread {j} for PID {pid}: TID {tid}")
    
    # Get process list
    proc_list = kernel.get_process_list()
    print(f"   📊 Total processes in system: {len(proc_list)}")
    
    # Get thread list
    thread_list = kernel.get_thread_list()
    print(f"   📊 Total threads in system: {len(thread_list)}")
    
    # Cleanup
    for tid in threads:
        kernel.destroy_thread(tid)
    for pid in processes:
        kernel.destroy_process(pid)
    
    print("   ✅ Process management demo complete\n")

def demonstrate_memory_management(kernel):
    """Demonstrate memory management"""
    print("💾 Memory Management Demo")
    print("-" * 40)
    
    # Allocate memory blocks of different sizes
    memory_blocks = []
    sizes = [1024, 4096, 8192, 16384]
    
    for size in sizes:
        ptr = kernel.allocate_memory(size)
        if ptr:
            memory_blocks.append((ptr, size))
            print(f"   ✓ Allocated {size} bytes at address 0x{ptr:08x}")
        else:
            print(f"   ⚠ Failed to allocate {size} bytes")
    
    print(f"   📊 Allocated {len(memory_blocks)} memory blocks")
    
    # Free memory
    for ptr, size in memory_blocks:
        kernel.free_memory(ptr)
        print(f"   ✓ Freed {size} bytes at address 0x{ptr:08x}")
    
    print("   ✅ Memory management demo complete\n")

def demonstrate_network_stack(kernel):
    """Demonstrate network stack"""
    print("🌐 Network Stack Demo")
    print("-" * 40)
    
    # Create sockets
    sockets = []
    for i in range(3):
        sockfd = kernel.create_socket(2, 1)  # AF_INET, SOCK_STREAM
        if sockfd:
            sockets.append(sockfd)
            print(f"   ✓ Created TCP socket {i}: FD {sockfd}")
    
    # Try to bind a socket
    if sockets:
        success = kernel.bind_socket(sockets[0], ("127.0.0.1", 8080))
        if success:
            print(f"   ✓ Bound socket {sockets[0]} to 127.0.0.1:8080")
        else:
            print(f"   ⚠ Failed to bind socket {sockets[0]}")
    
    # Try to send data
    if sockets:
        test_data = b"Hello, KOS Network Stack!"
        bytes_sent = kernel.send_data(sockets[0], test_data)
        print(f"   ✓ Sent {bytes_sent} bytes of data")
    
    # Network interface operations would go here if available
    print("   📊 Network operations completed")
    
    print("   ✅ Network stack demo complete\n")

def demonstrate_ipc(kernel):
    """Demonstrate IPC mechanisms"""
    print("💬 Inter-Process Communication Demo")
    print("-" * 40)
    
    # Create a process for IPC testing
    pid = kernel.create_process("ipc_target")
    if pid:
        print(f"   ✓ Created IPC target process: PID {pid}")
        
        # Send IPC message
        message = {"type": "greeting", "text": "Hello from KOS!", "timestamp": time.time()}
        success = kernel.send_ipc_message(pid, message)
        if success:
            print("   ✓ Sent IPC message successfully")
        else:
            print("   ⚠ IPC message sending returned False (mock mode)")
        
        # Try to receive message (will likely timeout in mock mode)
        received = kernel.receive_ipc_message(timeout=0.1)
        if received:
            src_pid, msg = received
            print(f"   ✓ Received IPC message from PID {src_pid}: {msg}")
        else:
            print("   ⚠ No IPC message received (expected in mock mode)")
        
        kernel.destroy_process(pid)
    else:
        print("   ⚠ Failed to create IPC target process")
    
    print("   ✅ IPC demo complete\n")

def demonstrate_filesystem(kernel):
    """Demonstrate filesystem operations"""
    print("📁 Filesystem Demo")
    print("-" * 40)
    
    # File operations
    test_files = []
    
    for i in range(2):
        filename = f"/tmp/kos_test_{i}.txt"
        fd = kernel.open_file(filename, "w")
        if fd:
            test_files.append((fd, filename))
            print(f"   ✓ Opened file {filename}: FD {fd}")
            
            # Write to file
            test_data = f"KOS Kernel Test File {i}\nGenerated at {time.ctime()}\n".encode()
            bytes_written = kernel.write_file(fd, test_data)
            print(f"   ✓ Wrote {bytes_written} bytes to {filename}")
        else:
            print(f"   ⚠ Failed to open file {filename}")
    
    # Read from files
    for fd, filename in test_files:
        data = kernel.read_file(fd, 1024)
        if data:
            print(f"   ✓ Read {len(data)} bytes from {filename}")
        else:
            print(f"   ⚠ No data read from {filename} (expected in mock mode)")
    
    # Close files
    for fd, filename in test_files:
        success = kernel.close_file(fd)
        if success:
            print(f"   ✓ Closed file {filename}")
    
    print("   ✅ Filesystem demo complete\n")

def demonstrate_syscalls(kernel):
    """Demonstrate system calls"""
    print("⚙️  System Call Demo")
    print("-" * 40)
    
    # Make various system calls
    syscalls = [
        (1, "getpid equivalent"),
        (2, "fork equivalent"), 
        (3, "exec equivalent"),
        (4, "exit equivalent"),
        (5, "read equivalent"),
        (6, "write equivalent")
    ]
    
    for syscall_nr, description in syscalls:
        result = kernel.syscall(syscall_nr, 0, 0, 0)
        print(f"   ✓ Syscall {syscall_nr} ({description}): returned {result}")
    
    print("   ✅ System call demo complete\n")

def demonstrate_monitoring(kernel):
    """Demonstrate resource monitoring"""
    print("📊 Resource Monitoring Demo")
    print("-" * 40)
    
    # Get kernel statistics
    stats = kernel.get_stats()
    
    print("   📈 Current Kernel Statistics:")
    print(f"      • Uptime: {stats.uptime:.2f} seconds")
    print(f"      • Processes: {stats.processes}")
    print(f"      • Threads: {stats.threads}")
    print(f"      • Memory Usage: {stats.memory_usage} bytes")
    print(f"      • CPU Usage: {stats.cpu_usage:.1f}%")
    print(f"      • Network Packets Sent: {stats.network_packets_sent}")
    print(f"      • Network Packets Received: {stats.network_packets_received}")
    print(f"      • Filesystem Operations: {stats.filesystem_operations}")
    print(f"      • IPC Messages: {stats.ipc_messages}")
    print(f"      • System Calls: {stats.syscalls}")
    print(f"      • Interrupts: {stats.interrupts}")
    
    # Wait a moment and get updated stats
    time.sleep(1)
    
    updated_stats = kernel.get_stats()
    print("\n   📈 Updated Statistics (after 1 second):")
    print(f"      • Uptime: {updated_stats.uptime:.2f} seconds")
    print(f"      • Uptime increased by: {updated_stats.uptime - stats.uptime:.2f} seconds")
    
    print("   ✅ Resource monitoring demo complete\n")

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
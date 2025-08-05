#!/usr/bin/env python3
"""
Comprehensive Test Suite for KOS Device Driver Framework

This script tests all aspects of the KOS device driver framework,
including character, block, network, and TTY devices.
"""

import sys
import os
import time
import threading
import random
from typing import List

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drivers_wrapper import (
    get_driver_manager,
    create_char_device,
    create_block_device,
    create_network_device,
    create_tty_device,
    destroy_device,
    list_devices,
    get_device,
    DeviceType,
    IOCTLCommands,
    KOSDriverError,
    DeviceNotFoundError,
    DeviceBusyError,
    InvalidParameterError
)

class TestResult:
    """Test result container"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def pass_test(self, name: str):
        self.passed += 1
        print(f"✓ {name}")
    
    def fail_test(self, name: str, error: str):
        self.failed += 1
        self.errors.append(f"{name}: {error}")
        print(f"✗ {name}: {error}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\nTest Summary: {self.passed}/{total} passed")
        if self.errors:
            print("\nFailures:")
            for error in self.errors:
                print(f"  - {error}")
        return self.failed == 0

def test_character_devices(result: TestResult):
    """Test character device functionality"""
    print("\n=== Character Device Tests ===")
    
    try:
        # Test device creation
        char_dev = create_char_device("test_char_1")
        result.pass_test("Character device creation")
        
        # Test basic I/O
        test_data = b"Hello, Character Device!"
        bytes_written = char_dev.write(test_data)
        if bytes_written == len(test_data):
            result.pass_test("Character device write")
        else:
            result.fail_test("Character device write", f"Expected {len(test_data)}, got {bytes_written}")
        
        read_data = char_dev.read()
        if read_data == test_data:
            result.pass_test("Character device read")
        else:
            result.fail_test("Character device read", f"Data mismatch: {read_data} != {test_data}")
        
        # Test partial read
        char_dev.write(b"1234567890")
        partial_data = char_dev.read(5)
        if partial_data == b"12345":
            result.pass_test("Character device partial read")
        else:
            result.fail_test("Character device partial read", f"Expected b'12345', got {partial_data}")
        
        # Test flush
        char_dev.flush()
        remaining = char_dev.read()
        if len(remaining) == 0:
            result.pass_test("Character device flush")
        else:
            result.fail_test("Character device flush", f"Data remaining after flush: {remaining}")
        
        # Test IOCTL
        info = char_dev.ioctl(IOCTLCommands.GET_INFO)
        if isinstance(info, dict) and 'buffer_size' in info:
            result.pass_test("Character device IOCTL")
        else:
            result.fail_test("Character device IOCTL", f"Invalid info response: {info}")
        
        # Test device destruction
        destroy_device("test_char_1")
        result.pass_test("Character device destruction")
        
    except Exception as e:
        result.fail_test("Character device test", str(e))

def test_block_devices(result: TestResult):
    """Test block device functionality"""
    print("\n=== Block Device Tests ===")
    
    try:
        # Test device creation
        size = 1024 * 1024  # 1MB
        block_size = 512
        block_dev = create_block_device("test_block_1", size, block_size)
        result.pass_test("Block device creation")
        
        # Verify device properties
        if block_dev.size == size and block_dev.block_size == block_size:
            result.pass_test("Block device properties")
        else:
            result.fail_test("Block device properties", 
                           f"Size: {block_dev.size}/{size}, Block size: {block_dev.block_size}/{block_size}")
        
        # Test block I/O
        test_block = b"A" * block_size
        bytes_written = block_dev.write_block(0, test_block)
        if bytes_written == block_size:
            result.pass_test("Block device write")
        else:
            result.fail_test("Block device write", f"Expected {block_size}, got {bytes_written}")
        
        read_block = block_dev.read_block(0)
        if read_block == test_block:
            result.pass_test("Block device read")
        else:
            result.fail_test("Block device read", "Block data mismatch")
        
        # Test random access
        for i in range(10):
            block_num = random.randint(0, block_dev.total_blocks - 1)
            data = bytes([i] * block_size)
            block_dev.write_block(block_num, data)
            
        # Verify random access
        for i in range(10):
            block_num = random.randint(0, block_dev.total_blocks - 1)
            data = block_dev.read_block(block_num)
            if len(data) == block_size:
                result.pass_test(f"Random access block {block_num}")
            else:
                result.fail_test(f"Random access block {block_num}", f"Invalid data length: {len(data)}")
        
        # Test offset I/O
        offset = 1000
        test_data = b"Offset test data"
        bytes_written = block_dev.write(offset, test_data)
        if bytes_written == len(test_data):
            result.pass_test("Block device offset write")
        else:
            result.fail_test("Block device offset write", f"Expected {len(test_data)}, got {bytes_written}")
        
        read_data = block_dev.read(offset, len(test_data))
        if read_data == test_data:
            result.pass_test("Block device offset read")
        else:
            result.fail_test("Block device offset read", "Offset data mismatch")
        
        # Test device info
        info = block_dev.get_info()
        if info.total_blocks == block_dev.total_blocks and info.block_size == block_size:
            result.pass_test("Block device info")
        else:
            result.fail_test("Block device info", "Info mismatch")
        
        # Test IOCTL
        total_blocks = block_dev.ioctl(IOCTLCommands.BLKGETSIZE)
        if total_blocks == block_dev.total_blocks:
            result.pass_test("Block device IOCTL")
        else:
            result.fail_test("Block device IOCTL", f"Expected {block_dev.total_blocks}, got {total_blocks}")
        
        # Test device destruction
        destroy_device("test_block_1")
        result.pass_test("Block device destruction")
        
    except Exception as e:
        result.fail_test("Block device test", str(e))

def test_network_devices(result: TestResult):
    """Test network device functionality"""
    print("\n=== Network Device Tests ===")
    
    try:
        # Test device creation with default MAC
        net_dev1 = create_network_device("test_net_1")
        result.pass_test("Network device creation (default MAC)")
        
        # Test device creation with custom MAC
        custom_mac = b"\x02\x00\x00\x00\x00\x01"
        net_dev2 = create_network_device("test_net_2", custom_mac)
        if net_dev2.mac_addr == custom_mac:
            result.pass_test("Network device creation (custom MAC)")
        else:
            result.fail_test("Network device creation (custom MAC)", "MAC address mismatch")
        
        # Test interface up/down
        net_dev1.up()
        if net_dev1.is_up:
            result.pass_test("Network interface up")
        else:
            result.fail_test("Network interface up", "Interface not up")
        
        net_dev1.down()
        if not net_dev1.is_up:
            result.pass_test("Network interface down")
        else:
            result.fail_test("Network interface down", "Interface still up")
        
        # Test packet operations
        net_dev1.up()
        test_packet = b"Test network packet data"
        
        try:
            bytes_sent = net_dev1.send_packet(test_packet)
            if bytes_sent == len(test_packet):
                result.pass_test("Network packet send")
            else:
                result.fail_test("Network packet send", f"Expected {len(test_packet)}, got {bytes_sent}")
        except Exception as e:
            result.fail_test("Network packet send", str(e))
        
        # Test packet injection and receive
        net_dev1.inject_packet(b"Injected packet")
        received = net_dev1.receive_packet()
        if received == b"Injected packet":
            result.pass_test("Network packet receive")
        else:
            result.fail_test("Network packet receive", f"Expected 'Injected packet', got {received}")
        
        # Test MTU operations
        try:
            net_dev1.set_mtu(9000)
            if net_dev1.mtu == 9000:
                result.pass_test("Network MTU set")
            else:
                result.fail_test("Network MTU set", f"MTU not set: {net_dev1.mtu}")
        except Exception as e:
            result.fail_test("Network MTU set", str(e))
        
        # Test invalid MTU
        try:
            net_dev1.set_mtu(10000)  # Too large
            result.fail_test("Network invalid MTU", "Should have raised exception")
        except InvalidParameterError:
            result.pass_test("Network invalid MTU handling")
        except Exception as e:
            result.fail_test("Network invalid MTU", f"Wrong exception: {e}")
        
        # Test statistics
        stats = net_dev1.get_stats()
        if stats.tx_packets > 0:
            result.pass_test("Network statistics")
        else:
            result.fail_test("Network statistics", "No TX packets recorded")
        
        # Test device info
        info = net_dev1.get_info()
        if info.mac_addr == net_dev1.mac_addr and info.mtu == net_dev1.mtu:
            result.pass_test("Network device info")
        else:
            result.fail_test("Network device info", "Info mismatch")
        
        # Test IOCTL operations
        net_dev1.ioctl(IOCTLCommands.NETDOWN)
        if not net_dev1.is_up:
            result.pass_test("Network IOCTL down")
        else:
            result.fail_test("Network IOCTL down", "Interface still up")
        
        net_dev1.ioctl(IOCTLCommands.NETUP)
        if net_dev1.is_up:
            result.pass_test("Network IOCTL up")
        else:
            result.fail_test("Network IOCTL up", "Interface not up")
        
        # Test device destruction
        destroy_device("test_net_1")
        destroy_device("test_net_2")
        result.pass_test("Network device destruction")
        
    except Exception as e:
        result.fail_test("Network device test", str(e))

def test_tty_devices(result: TestResult):
    """Test TTY device functionality"""
    print("\n=== TTY Device Tests ===")
    
    try:
        # Test device creation
        tty_dev = create_tty_device("test_tty_1")
        result.pass_test("TTY device creation")
        
        # Test character input in canonical mode
        tty_dev.input_char('H')
        tty_dev.input_char('e')
        tty_dev.input_char('l')
        tty_dev.input_char('l')
        tty_dev.input_char('o')
        tty_dev.input_char('\n')
        
        line = tty_dev.read_line()
        if line == "Hello\n":
            result.pass_test("TTY canonical input")
        else:
            result.fail_test("TTY canonical input", f"Expected 'Hello\\n', got {repr(line)}")
        
        # Test backspace in canonical mode
        tty_dev.input_char('T')
        tty_dev.input_char('e')
        tty_dev.input_char('s')
        tty_dev.input_char('t')
        tty_dev.input_char('\b')  # Backspace
        tty_dev.input_char('x')
        tty_dev.input_char('\n')
        
        line = tty_dev.read_line()
        if line == "Tesx\n":
            result.pass_test("TTY backspace handling")
        else:
            result.fail_test("TTY backspace handling", f"Expected 'Tesx\\n', got {repr(line)}")
        
        # Test output
        text = "Hello from TTY!\n"
        bytes_written = tty_dev.write(text)
        if bytes_written == len(text):
            result.pass_test("TTY output write")
        else:
            result.fail_test("TTY output write", f"Expected {len(text)}, got {bytes_written}")
        
        output = tty_dev.read_output()
        if text in output:  # Echo might add extra characters
            result.pass_test("TTY output read")
        else:
            result.fail_test("TTY output read", f"Expected '{text}' in output, got {repr(output)}")
        
        # Test raw mode
        tty_dev.set_raw_mode()
        if not tty_dev.canonical and not tty_dev.echo:
            result.pass_test("TTY raw mode")
        else:
            result.fail_test("TTY raw mode", "Mode not properly set")
        
        # Test cooked mode
        tty_dev.set_cooked_mode()
        if tty_dev.canonical and tty_dev.echo:
            result.pass_test("TTY cooked mode")
        else:
            result.fail_test("TTY cooked mode", "Mode not properly set")
        
        # Test window size
        tty_dev.set_window_size(25, 132)
        if tty_dev.rows == 25 and tty_dev.cols == 132:
            result.pass_test("TTY window size")
        else:
            result.fail_test("TTY window size", f"Expected 25x132, got {tty_dev.rows}x{tty_dev.cols}")
        
        # Test device info
        info = tty_dev.get_info()
        if info.rows == 25 and info.cols == 132:
            result.pass_test("TTY device info")
        else:
            result.fail_test("TTY device info", "Info mismatch")
        
        # Test IOCTL operations
        tty_dev.ioctl(IOCTLCommands.TTYSETRAW)
        if not tty_dev.canonical:
            result.pass_test("TTY IOCTL raw")
        else:
            result.fail_test("TTY IOCTL raw", "Still in canonical mode")
        
        tty_dev.ioctl(IOCTLCommands.TTYSETCOOKED)
        if tty_dev.canonical:
            result.pass_test("TTY IOCTL cooked")
        else:
            result.fail_test("TTY IOCTL cooked", "Not in canonical mode")
        
        # Test device destruction
        destroy_device("test_tty_1")
        result.pass_test("TTY device destruction")
        
    except Exception as e:
        result.fail_test("TTY device test", str(e))

def test_error_handling(result: TestResult):
    """Test error handling and edge cases"""
    print("\n=== Error Handling Tests ===")
    
    try:
        # Test duplicate device creation
        char_dev = create_char_device("duplicate_test")
        try:
            create_char_device("duplicate_test")
            result.fail_test("Duplicate device prevention", "Should have raised exception")
        except DeviceBusyError:
            result.pass_test("Duplicate device prevention")
        except Exception as e:
            result.fail_test("Duplicate device prevention", f"Wrong exception: {e}")
        
        destroy_device("duplicate_test")
        
        # Test device not found
        try:
            destroy_device("nonexistent_device")
            result.fail_test("Device not found handling", "Should have raised exception")
        except DeviceNotFoundError:
            result.pass_test("Device not found handling")
        except Exception as e:
            result.fail_test("Device not found handling", f"Wrong exception: {e}")
        
        # Test invalid parameters
        try:
            create_block_device("invalid_block", 0, 512)  # Zero size
            result.fail_test("Invalid block size handling", "Should have raised exception")
        except (InvalidParameterError, ValueError):
            result.pass_test("Invalid block size handling")
        except Exception as e:
            result.fail_test("Invalid block size handling", f"Wrong exception: {e}")
        
        # Test invalid MAC address
        try:
            create_network_device("invalid_net", b"invalid")  # Wrong length
            result.fail_test("Invalid MAC address handling", "Should have raised exception")
        except InvalidParameterError:
            result.pass_test("Invalid MAC address handling")
        except Exception as e:
            result.fail_test("Invalid MAC address handling", f"Wrong exception: {e}")
        
    except Exception as e:
        result.fail_test("Error handling test", str(e))

def stress_test_devices(result: TestResult):
    """Perform stress testing on devices"""
    print("\n=== Stress Tests ===")
    
    try:
        # Create multiple devices
        devices = []
        for i in range(10):
            char_dev = create_char_device(f"stress_char_{i}")
            block_dev = create_block_device(f"stress_block_{i}", 64 * 1024, 512)
            net_dev = create_network_device(f"stress_net_{i}")
            tty_dev = create_tty_device(f"stress_tty_{i}")
            devices.extend([char_dev, block_dev, net_dev, tty_dev])
        
        result.pass_test("Multiple device creation")
        
        # Test concurrent access
        def worker_thread(device_list, thread_id):
            for device in device_list:
                if hasattr(device, 'write') and hasattr(device, 'read'):
                    try:
                        if hasattr(device, 'write_block'):
                            # Block device
                            data = bytes([thread_id] * device.block_size)
                            device.write_block(0, data)
                            device.read_block(0)
                        else:
                            # Character or TTY device
                            data = f"Thread {thread_id} data".encode()
                            device.write(data)
                            device.read() if hasattr(device, 'read') else None
                    except Exception:
                        pass  # Ignore errors in stress test
        
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker_thread, args=(devices[:4], i))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        result.pass_test("Concurrent device access")
        
        # Cleanup all devices
        for i in range(10):
            destroy_device(f"stress_char_{i}")
            destroy_device(f"stress_block_{i}")
            destroy_device(f"stress_net_{i}")
            destroy_device(f"stress_tty_{i}")
        
        result.pass_test("Stress test cleanup")
        
    except Exception as e:
        result.fail_test("Stress test", str(e))

def test_device_manager(result: TestResult):
    """Test device manager functionality"""
    print("\n=== Device Manager Tests ===")
    
    try:
        manager = get_driver_manager()
        
        # Test device listing
        initial_devices = manager.list_devices()
        
        # Create some devices
        char_dev = manager.create_char_device("manager_char")
        block_dev = manager.create_block_device("manager_block", 1024, 512)
        
        # Verify device listing
        devices = manager.list_devices()
        if len(devices) == len(initial_devices) + 2:
            result.pass_test("Device manager listing")
        else:
            result.fail_test("Device manager listing", 
                           f"Expected {len(initial_devices) + 2} devices, got {len(devices)}")
        
        # Test device retrieval
        retrieved_char = manager.get_device("manager_char")
        if retrieved_char is char_dev:
            result.pass_test("Device manager retrieval")
        else:
            result.fail_test("Device manager retrieval", "Device mismatch")
        
        # Test device destruction
        manager.destroy_device("manager_char")
        manager.destroy_device("manager_block")
        
        final_devices = manager.list_devices()
        if len(final_devices) == len(initial_devices):
            result.pass_test("Device manager cleanup")
        else:
            result.fail_test("Device manager cleanup", 
                           f"Expected {len(initial_devices)} devices, got {len(final_devices)}")
        
    except Exception as e:
        result.fail_test("Device manager test", str(e))

def performance_benchmark(result: TestResult):
    """Run performance benchmarks"""
    print("\n=== Performance Benchmarks ===")
    
    try:
        # Character device performance
        char_dev = create_char_device("perf_char")
        
        start_time = time.time()
        for i in range(1000):
            char_dev.write(b"Performance test data")
            char_dev.read()
        char_time = time.time() - start_time
        
        print(f"Character device: 1000 write/read cycles in {char_time:.3f}s")
        result.pass_test("Character device performance")
        
        # Block device performance
        block_dev = create_block_device("perf_block", 1024 * 1024, 512)
        test_block = b"X" * 512
        
        start_time = time.time()
        for i in range(1000):
            block_dev.write_block(i % block_dev.total_blocks, test_block)
            block_dev.read_block(i % block_dev.total_blocks)
        block_time = time.time() - start_time
        
        print(f"Block device: 1000 block operations in {block_time:.3f}s")
        result.pass_test("Block device performance")
        
        # Network device performance
        net_dev = create_network_device("perf_net")
        net_dev.up()
        test_packet = b"Performance packet data"
        
        start_time = time.time()
        for i in range(1000):
            net_dev.send_packet(test_packet)
            net_dev.inject_packet(test_packet)
            net_dev.receive_packet()
        net_time = time.time() - start_time
        
        print(f"Network device: 1000 packet operations in {net_time:.3f}s")
        result.pass_test("Network device performance")
        
        # Cleanup
        destroy_device("perf_char")
        destroy_device("perf_block")
        destroy_device("perf_net")
        
    except Exception as e:
        result.fail_test("Performance benchmark", str(e))

def main():
    """Main test runner"""
    print("KOS Device Driver Framework Test Suite")
    print("=" * 50)
    
    result = TestResult()
    
    # Run all test suites
    test_character_devices(result)
    test_block_devices(result)
    test_network_devices(result)
    test_tty_devices(result)
    test_error_handling(result)
    test_device_manager(result)
    stress_test_devices(result)
    performance_benchmark(result)
    
    # Print summary
    success = result.summary()
    
    # Clean up any remaining devices
    remaining_devices = list_devices()
    if remaining_devices:
        print(f"\nCleaning up {len(remaining_devices)} remaining devices...")
        for device_name in remaining_devices:
            try:
                destroy_device(device_name)
            except Exception:
                pass
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
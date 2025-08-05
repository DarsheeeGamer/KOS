#!/usr/bin/env python3
"""
Simple test for KOS Device Driver Framework
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_basic_functionality():
    print("Testing KOS Device Driver Framework...")
    
    try:
        # Import the module
        import drivers_wrapper
        print("✓ Module imported successfully")
        
        # Test character device
        print("\nTesting Character Device:")
        char_dev = drivers_wrapper.create_char_device("test_char")
        print(f"✓ Created character device: {char_dev.name}")
        
        # Write data
        test_data = b"Hello, KOS Drivers!"
        bytes_written = char_dev.write(test_data)
        print(f"✓ Wrote {bytes_written} bytes")
        
        # Read data back
        read_data = char_dev.read()
        if read_data == test_data:
            print("✓ Data read back correctly")
        else:
            print(f"✗ Data mismatch: {read_data} != {test_data}")
        
        # Test IOCTL
        info = char_dev.ioctl(drivers_wrapper.IOCTLCommands.GET_INFO)
        print(f"✓ IOCTL returned: {info}")
        
        # Clean up
        drivers_wrapper.destroy_device("test_char")
        print("✓ Character device destroyed")
        
        # Test block device
        print("\nTesting Block Device:")
        block_dev = drivers_wrapper.create_block_device("test_block", 1024, 512)
        print(f"✓ Created block device: {block_dev.name} ({block_dev.total_blocks} blocks)")
        
        # Write a block
        block_data = b"A" * 512
        block_dev.write_block(0, block_data)
        print("✓ Wrote block 0")
        
        # Read the block back
        read_block = block_dev.read_block(0)
        if read_block == block_data:
            print("✓ Block read back correctly")
        else:
            print("✗ Block data mismatch")
        
        # Clean up
        drivers_wrapper.destroy_device("test_block")
        print("✓ Block device destroyed")
        
        # Test network device
        print("\nTesting Network Device:")
        net_dev = drivers_wrapper.create_network_device("test_net")
        print(f"✓ Created network device: {net_dev.name}")
        print(f"  MAC Address: {net_dev.mac_addr.hex(':').upper()}")
        
        # Bring interface up
        net_dev.up()
        print("✓ Interface brought up")
        
        # Send a packet
        packet = b"Test network packet"
        net_dev.send_packet(packet)
        print("✓ Packet sent")
        
        # Inject and receive a packet
        net_dev.inject_packet(b"Received packet")
        received = net_dev.receive_packet()
        if received:
            print(f"✓ Received packet: {received}")
        else:
            print("✗ No packet received")
        
        # Clean up
        drivers_wrapper.destroy_device("test_net")
        print("✓ Network device destroyed")
        
        # Test TTY device
        print("\nTesting TTY Device:")
        tty_dev = drivers_wrapper.create_tty_device("test_tty")
        print(f"✓ Created TTY device: {tty_dev.name}")
        
        # Input some characters
        for char in "Hello\n":
            tty_dev.input_char(char)
        
        # Read the line
        line = tty_dev.read_line()
        if line:
            print(f"✓ Read line: {repr(line)}")
        else:
            print("✗ No line read")
        
        # Write output
        tty_dev.write("TTY Output\n")
        output = tty_dev.read_output()
        print(f"✓ TTY output: {repr(output)}")
        
        # Clean up
        drivers_wrapper.destroy_device("test_tty")
        print("✓ TTY device destroyed")
        
        print("\n✓ All tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_basic_functionality()
    sys.exit(0 if success else 1)
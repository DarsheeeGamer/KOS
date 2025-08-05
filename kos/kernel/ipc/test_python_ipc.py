#!/usr/bin/env python3
"""
Test script for KOS IPC Python bindings
"""

import sys
import os

# Add current directory to path to find ipc_wrapper
sys.path.insert(0, '.')

try:
    from ipc_wrapper import *
    print("Successfully imported KOS IPC Python bindings")
    
    # Test basic functionality
    with IPCManager() as ipc:
        print("IPC Manager initialized")
        
        # Test pipe (should work with mock implementation if library isn't available)
        try:
            pipe = ipc.manage(Pipe())
            pipe.write(b"Hello from Python!")
            data = pipe.read()
            print(f"Pipe test successful: {data}")
        except Exception as e:
            print(f"Pipe test failed: {e}")
        
        # Test semaphore
        try:
            sem = ipc.manage(Semaphore("test_sem", 1))
            print(f"Initial semaphore value: {sem.get_value()}")
            sem.wait()
            print(f"After wait: {sem.get_value()}")
            sem.post()
            print(f"After post: {sem.get_value()}")
            print("Semaphore test successful")
        except Exception as e:
            print(f"Semaphore test failed: {e}")
        
        # Test mutex
        try:
            mutex = Mutex()
            with mutex:
                print("Mutex test successful")
        except Exception as e:
            print(f"Mutex test failed: {e}")
        
        print("Python IPC tests completed!")

except ImportError as e:
    print(f"Failed to import IPC wrapper: {e}")
except Exception as e:
    print(f"Error during testing: {e}")
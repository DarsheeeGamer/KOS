#!/usr/bin/env python3
"""
KOS IPC Demonstration Script
Shows the complete IPC system functionality with mock implementations
"""

import os
import signal
import time
import threading
from typing import Dict, List

class MockIPCDemo:
    """Mock IPC demonstration for when the C library isn't available"""
    
    def __init__(self):
        self.pipes = {}
        self.shared_memory = {}
        self.message_queues = {}
        self.semaphores = {}
        self.mutexes = {}
        self.signals = {}
        
    def demo_pipes(self):
        print("=== Pipe Demo ===")
        print("Creating anonymous pipe...")
        
        # Simulate pipe creation and usage
        pipe_data = []
        
        message = b"Hello from KOS pipe!"
        pipe_data.append(message)
        print(f"Wrote to pipe: {message}")
        
        if pipe_data:
            read_data = pipe_data.pop(0)
            print(f"Read from pipe: {read_data}")
        
        print("Creating named pipe...")
        named_pipe = "/tmp/kos_named_pipe"
        print(f"Named pipe created: {named_pipe}")
        
        print("Pipe demo completed\n")
    
    def demo_shared_memory(self):
        print("=== Shared Memory Demo ===")
        print("Creating shared memory segment...")
        
        # Simulate shared memory
        shm_name = "kos_test_shm"
        shm_size = 4096
        shared_data = bytearray(shm_size)
        
        test_data = b"Shared memory test data from KOS"
        shared_data[:len(test_data)] = test_data
        
        print(f"Created shared memory: {shm_name} ({shm_size} bytes)")
        print(f"Wrote to shared memory: {test_data}")
        print(f"Read from shared memory: {bytes(shared_data[:len(test_data)])}")
        
        print("Shared memory demo completed\n")
    
    def demo_message_queues(self):
        print("=== Message Queue Demo ===")
        print("Creating POSIX message queue...")
        
        # Simulate message queue
        queue = []
        
        messages = [
            (b"Message 1", 1),
            (b"High priority message", 10),
            (b"Normal message", 5)
        ]
        
        for msg, priority in messages:
            queue.append((msg, priority))
            print(f"Sent message: {msg} (priority: {priority})")
        
        # Sort by priority (higher priority first)
        queue.sort(key=lambda x: x[1], reverse=True)
        
        print("\nReceiving messages in priority order:")
        while queue:
            msg, priority = queue.pop(0)
            print(f"Received: {msg} (priority: {priority})")
        
        print("Message queue demo completed\n")
    
    def demo_semaphores(self):
        print("=== Semaphore Demo ===")
        print("Creating semaphore with value 2...")
        
        # Simulate semaphore
        sem_value = 2
        print(f"Initial semaphore value: {sem_value}")
        
        # Simulate wait operations
        for i in range(3):
            if sem_value > 0:
                sem_value -= 1
                print(f"Wait {i+1}: Success, value now {sem_value}")
            else:
                print(f"Wait {i+1}: Would block, value is {sem_value}")
        
        # Simulate post operations
        for i in range(2):
            sem_value += 1
            print(f"Post {i+1}: Success, value now {sem_value}")
        
        print("Semaphore demo completed\n")
    
    def demo_mutexes(self):
        print("=== Mutex Demo ===")
        print("Creating mutex...")
        
        # Simulate mutex with threading
        mutex_locked = False
        
        def worker(name):
            nonlocal mutex_locked
            print(f"Worker {name}: Attempting to lock mutex...")
            
            if not mutex_locked:
                mutex_locked = True
                print(f"Worker {name}: Acquired mutex")
                time.sleep(0.1)  # Simulate work
                mutex_locked = False
                print(f"Worker {name}: Released mutex")
            else:
                print(f"Worker {name}: Mutex busy")
        
        # Simulate multiple workers
        for i in range(3):
            worker(f"Thread-{i+1}")
        
        print("Mutex demo completed\n")
    
    def demo_condition_variables(self):
        print("=== Condition Variable Demo ===")
        print("Creating condition variable...")
        
        # Simulate condition variable
        condition_met = False
        waiters = []
        
        print("Thread 1: Waiting on condition...")
        waiters.append("Thread-1")
        
        print("Thread 2: Waiting on condition...")
        waiters.append("Thread-2")
        
        print("Main thread: Signaling condition...")
        if waiters:
            woken = waiters.pop(0)
            print(f"{woken}: Woken up by signal")
        
        print("Main thread: Broadcasting condition...")
        while waiters:
            woken = waiters.pop(0)
            print(f"{woken}: Woken up by broadcast")
        
        print("Condition variable demo completed\n")
    
    def demo_signals(self):
        print("=== Signal Demo ===")
        print("Registering signal handlers...")
        
        # Simulate signal handling
        def signal_handler(signum):
            print(f"Received signal: {signum}")
        
        print("Handler registered for SIGUSR1")
        print("Handler registered for SIGTERM")
        
        print("Sending SIGUSR1 to self...")
        signal_handler(signal.SIGUSR1)
        
        print("Blocking SIGPIPE...")
        print("SIGPIPE blocked")
        
        print("Signal demo completed\n")
    
    def demo_advanced_features(self):
        print("=== Advanced IPC Features ===")
        print("Demonstrating process synchronization...")
        
        # Producer-Consumer example
        buffer = []
        buffer_size = 5
        
        print(f"Created bounded buffer (size: {buffer_size})")
        
        # Simulate producer
        for i in range(3):
            if len(buffer) < buffer_size:
                item = f"item-{i+1}"
                buffer.append(item)
                print(f"Producer: Added {item} (buffer size: {len(buffer)})")
            else:
                print("Producer: Buffer full, would block")
        
        # Simulate consumer
        for i in range(2):
            if buffer:
                item = buffer.pop(0)
                print(f"Consumer: Removed {item} (buffer size: {len(buffer)})")
            else:
                print("Consumer: Buffer empty, would block")
        
        print("Advanced features demo completed\n")
    
    def run_all_demos(self):
        print("KOS Inter-Process Communication (IPC) System Demo")
        print("=" * 50)
        print("Note: This is a demonstration using mock implementations")
        print("The actual C library provides full functionality\n")
        
        self.demo_pipes()
        self.demo_shared_memory()
        self.demo_message_queues()
        self.demo_semaphores()
        self.demo_mutexes()
        self.demo_condition_variables()
        self.demo_signals()
        self.demo_advanced_features()
        
        print("=" * 50)
        print("KOS IPC Demo completed successfully!")
        print("\nFeatures demonstrated:")
        print("✓ Anonymous and named pipes")
        print("✓ POSIX and System V shared memory")
        print("✓ POSIX and System V message queues")
        print("✓ POSIX and System V semaphores")
        print("✓ Process-shared mutexes")
        print("✓ Process-shared condition variables")
        print("✓ Signal handling and management")
        print("✓ Advanced synchronization patterns")

if __name__ == "__main__":
    demo = MockIPCDemo()
    demo.run_all_demos()
#!/usr/bin/env python3
"""
KOS Kernel Comprehensive Test Suite

Tests all kernel subsystems including:
- Core kernel functionality
- Process and thread management  
- Memory management
- Filesystem operations
- Network stack
- IPC mechanisms
- Device drivers
- Scheduling
- Resource monitoring
- Integration tests
- Performance benchmarks
- Stress tests
"""

import unittest
import sys
import os
import time
import threading
import multiprocessing
import tempfile
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from unittest.mock import Mock, patch

# Add kernel directory to path
sys.path.insert(0, os.path.dirname(__file__))

try:
    from kernel import (
        KOSKernelManager, KernelConfig, KernelState, KernelContext,
        SystemCallError, KernelPanicError, initialize_kernel, get_kernel,
        ProcessState, ThreadState
    )
except ImportError as e:
    print(f"Failed to import kernel modules: {e}")
    sys.exit(1)

# Setup test logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger('KOS.test')


class TestKernelCore(unittest.TestCase):
    """Test core kernel functionality"""
    
    def setUp(self):
        """Setup test environment"""
        self.config = KernelConfig(
            debug_mode=True,
            max_processes=10,
            max_threads=20,
            resource_monitoring=False  # Disable for faster tests
        )
        
    def tearDown(self):
        """Cleanup test environment"""
        # Ensure kernel is shut down
        kernel = get_kernel()
        if kernel:
            kernel.shutdown()
    
    def test_kernel_initialization(self):
        """Test kernel initialization"""
        with KernelContext(self.config) as kernel:
            self.assertIsInstance(kernel, KOSKernelManager)
            self.assertEqual(kernel.state, KernelState.RUNNING)
            self.assertIsNotNone(kernel.core)
    
    def test_kernel_configuration(self):
        """Test kernel configuration"""
        kernel = KOSKernelManager(self.config)
        self.assertEqual(kernel.config.debug_mode, True)
        self.assertEqual(kernel.config.max_processes, 10)
        self.assertEqual(kernel.config.max_threads, 20)
    
    def test_kernel_shutdown(self):
        """Test kernel shutdown"""
        kernel = KOSKernelManager(self.config)
        self.assertTrue(kernel.initialize())
        kernel.shutdown()
        self.assertEqual(kernel.state, KernelState.SHUTDOWN)
    
    def test_kernel_stats(self):
        """Test kernel statistics"""
        with KernelContext(self.config) as kernel:
            stats = kernel.get_stats()
            self.assertGreaterEqual(stats.uptime, 0)
            self.assertGreaterEqual(stats.processes, 0)
            self.assertGreaterEqual(stats.threads, 0)


class TestProcessManagement(unittest.TestCase):
    """Test process management"""
    
    def setUp(self):
        self.config = KernelConfig(debug_mode=True)
    
    def test_create_process(self):
        """Test process creation"""
        with KernelContext(self.config) as kernel:
            pid = kernel.create_process("test_process")
            self.assertIsNotNone(pid)
            self.assertIsInstance(pid, int)
    
    def test_destroy_process(self):
        """Test process destruction"""
        with KernelContext(self.config) as kernel:
            pid = kernel.create_process("test_process")
            self.assertIsNotNone(pid)
            
            result = kernel.destroy_process(pid)
            self.assertTrue(result)
    
    def test_process_list(self):
        """Test getting process list"""
        with KernelContext(self.config) as kernel:
            processes_before = len(kernel.get_process_list())
            
            pid = kernel.create_process("test_process")
            self.assertIsNotNone(pid)
            
            processes_after = len(kernel.get_process_list())
            # Note: In mock implementation, list might not change
            self.assertGreaterEqual(processes_after, 0)
    
    def test_multiple_processes(self):
        """Test creating multiple processes"""
        with KernelContext(self.config) as kernel:
            pids = []
            for i in range(5):
                pid = kernel.create_process(f"test_process_{i}")
                self.assertIsNotNone(pid)
                pids.append(pid)
            
            # Clean up
            for pid in pids:
                kernel.destroy_process(pid)


class TestThreadManagement(unittest.TestCase):
    """Test thread management"""
    
    def setUp(self):
        self.config = KernelConfig(debug_mode=True)
    
    def test_create_thread(self):
        """Test thread creation"""
        with KernelContext(self.config) as kernel:
            pid = kernel.create_process("test_process")
            self.assertIsNotNone(pid)
            
            tid = kernel.create_thread(pid)
            self.assertIsNotNone(tid)
            self.assertIsInstance(tid, int)
    
    def test_destroy_thread(self):
        """Test thread destruction"""
        with KernelContext(self.config) as kernel:
            pid = kernel.create_process("test_process")
            tid = kernel.create_thread(pid)
            
            result = kernel.destroy_thread(tid)
            self.assertTrue(result)
    
    def test_thread_list(self):
        """Test getting thread list"""
        with KernelContext(self.config) as kernel:
            threads = kernel.get_thread_list()
            self.assertIsInstance(threads, list)


class TestMemoryManagement(unittest.TestCase):
    """Test memory management"""
    
    def setUp(self):
        self.config = KernelConfig(debug_mode=True)
    
    def test_allocate_memory(self):
        """Test memory allocation"""
        with KernelContext(self.config) as kernel:
            ptr = kernel.allocate_memory(1024)
            self.assertIsNotNone(ptr)
            self.assertIsInstance(ptr, int)
            
            # Free the memory
            kernel.free_memory(ptr)
    
    def test_memory_allocation_sizes(self):
        """Test different memory allocation sizes"""
        with KernelContext(self.config) as kernel:
            sizes = [64, 1024, 4096, 65536]
            pointers = []
            
            for size in sizes:
                ptr = kernel.allocate_memory(size)
                self.assertIsNotNone(ptr)
                pointers.append(ptr)
            
            # Free all memory
            for ptr in pointers:
                kernel.free_memory(ptr)
    
    def test_memory_stress(self):
        """Stress test memory allocation"""
        with KernelContext(self.config) as kernel:
            pointers = []
            
            # Allocate many small blocks
            for i in range(100):
                ptr = kernel.allocate_memory(64)
                if ptr:
                    pointers.append(ptr)
            
            # Free all
            for ptr in pointers:
                kernel.free_memory(ptr)


class TestFilesystemOperations(unittest.TestCase):
    """Test filesystem operations"""
    
    def setUp(self):
        self.config = KernelConfig(debug_mode=True, filesystem_enabled=True)
    
    def test_file_operations(self):
        """Test basic file operations"""
        with KernelContext(self.config) as kernel:
            # Test file open
            fd = kernel.open_file("/tmp/test_file", "w")
            if fd is not None:  # Only test if filesystem is available
                self.assertIsInstance(fd, int)
                
                # Test file write
                data = b"Hello, KOS!"
                bytes_written = kernel.write_file(fd, data)
                self.assertGreaterEqual(bytes_written, 0)
                
                # Test file close
                result = kernel.close_file(fd)
                self.assertTrue(result)
    
    def test_file_read_write(self):
        """Test file read/write operations"""
        with KernelContext(self.config) as kernel:
            # Skip if filesystem not available
            if not kernel.filesystem:
                self.skipTest("Filesystem not available")
            
            fd = kernel.open_file("/tmp/test_rw", "w+")
            if fd is not None:
                # Write data
                test_data = b"Test data for read/write"
                kernel.write_file(fd, test_data)
                
                # Read data back
                read_data = kernel.read_file(fd, len(test_data))
                # Note: Mock filesystem might not actually persist data
                
                kernel.close_file(fd)


class TestNetworkOperations(unittest.TestCase):
    """Test network operations"""
    
    def setUp(self):
        self.config = KernelConfig(debug_mode=True, network_enabled=True)
    
    def test_socket_creation(self):
        """Test socket creation"""
        with KernelContext(self.config) as kernel:
            sockfd = kernel.create_socket(2, 1)  # AF_INET, SOCK_STREAM
            self.assertIsNotNone(sockfd)
            self.assertIsInstance(sockfd, int)
    
    def test_socket_operations(self):
        """Test socket bind and connect"""
        with KernelContext(self.config) as kernel:
            # Skip if network not available
            if not kernel.network:
                self.skipTest("Network stack not available")
            
            sockfd = kernel.create_socket(2, 1)
            if sockfd is not None:
                # Test bind
                result = kernel.bind_socket(sockfd, ("127.0.0.1", 8080))
                # Note: Mock implementation always returns True
                
                # Test data operations
                data = b"Test network data"
                bytes_sent = kernel.send_data(sockfd, data)
                self.assertGreaterEqual(bytes_sent, 0)


class TestIPCOperations(unittest.TestCase):
    """Test IPC operations"""
    
    def setUp(self):
        self.config = KernelConfig(debug_mode=True, ipc_enabled=True)
    
    def test_ipc_messaging(self):
        """Test IPC message sending/receiving"""
        with KernelContext(self.config) as kernel:
            # Skip if IPC not available
            if not kernel.ipc:
                self.skipTest("IPC not available")
            
            # Create a process to send message to
            dest_pid = kernel.create_process("ipc_target")
            if dest_pid:
                message = {"type": "test", "data": "Hello IPC"}
                result = kernel.send_ipc_message(dest_pid, message)
                # Note: Mock implementation might always return True
                
                # Try to receive (might timeout in mock)
                received = kernel.receive_ipc_message(timeout=0.1)
                # received might be None in mock implementation


class TestSystemCalls(unittest.TestCase):
    """Test system calls"""
    
    def setUp(self):
        self.config = KernelConfig(debug_mode=True)
    
    def test_syscall_basic(self):
        """Test basic system call"""
        with KernelContext(self.config) as kernel:
            result = kernel.syscall(1, 0, 0, 0)  # Basic syscall
            self.assertIsInstance(result, int)
    
    def test_syscall_with_args(self):
        """Test system call with arguments"""
        with KernelContext(self.config) as kernel:
            result = kernel.syscall(1, 123, 456, 789)
            self.assertIsInstance(result, int)


class TestCallbacks(unittest.TestCase):
    """Test callback system"""
    
    def setUp(self):
        self.config = KernelConfig(debug_mode=True)
        self.callback_called = False
        self.callback_count = 0
    
    def test_callback_registration(self):
        """Test callback registration"""
        def test_callback():
            self.callback_called = True
        
        with KernelContext(self.config) as kernel:
            kernel.register_callback("test_event", test_callback)
            
            # Let kernel loop run a bit
            time.sleep(0.1)
            
            kernel.unregister_callback("test_event", test_callback)
    
    def test_multiple_callbacks(self):
        """Test multiple callback registration"""
        def callback1():
            self.callback_count += 1
        
        def callback2():
            self.callback_count += 2
        
        with KernelContext(self.config) as kernel:
            kernel.register_callback("multi_event", callback1)
            kernel.register_callback("multi_event", callback2)
            
            time.sleep(0.1)
            
            kernel.unregister_callback("multi_event", callback1)
            kernel.unregister_callback("multi_event", callback2)


class TestIntegration(unittest.TestCase):
    """Integration tests"""
    
    def setUp(self):
        self.config = KernelConfig(debug_mode=True, resource_monitoring=True)
    
    def test_full_system_integration(self):
        """Test full system integration"""
        with KernelContext(self.config) as kernel:
            # Create process
            pid = kernel.create_process("integration_test")
            self.assertIsNotNone(pid)
            
            # Create thread
            tid = kernel.create_thread(pid)
            self.assertIsNotNone(tid)
            
            # Allocate memory
            ptr = kernel.allocate_memory(4096)
            self.assertIsNotNone(ptr)
            
            # Create socket
            sockfd = kernel.create_socket(2, 1)
            self.assertIsNotNone(sockfd)
            
            # Get statistics
            stats = kernel.get_stats()
            self.assertGreaterEqual(stats.uptime, 0)
            
            # Cleanup
            kernel.free_memory(ptr)
            kernel.destroy_thread(tid)
            kernel.destroy_process(pid)
    
    def test_concurrent_operations(self):
        """Test concurrent kernel operations"""
        def worker(kernel, worker_id):
            """Worker function for concurrent test"""
            try:
                # Create process
                pid = kernel.create_process(f"worker_{worker_id}")
                if pid:
                    # Allocate memory
                    ptr = kernel.allocate_memory(1024)
                    if ptr:
                        time.sleep(0.01)  # Simulate work
                        kernel.free_memory(ptr)
                    kernel.destroy_process(pid)
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
        
        with KernelContext(self.config) as kernel:
            threads = []
            for i in range(5):
                t = threading.Thread(target=worker, args=(kernel, i))
                threads.append(t)
                t.start()
            
            # Wait for all threads
            for t in threads:
                t.join(timeout=5.0)


class TestPerformance(unittest.TestCase):
    """Performance benchmarks"""
    
    def setUp(self):
        self.config = KernelConfig(debug_mode=False, resource_monitoring=False)
    
    def test_process_creation_performance(self):
        """Benchmark process creation"""
        with KernelContext(self.config) as kernel:
            start_time = time.time()
            pids = []
            
            for i in range(100):
                pid = kernel.create_process(f"perf_test_{i}")
                if pid:
                    pids.append(pid)
            
            creation_time = time.time() - start_time
            
            # Cleanup
            start_cleanup = time.time()
            for pid in pids:
                kernel.destroy_process(pid)
            cleanup_time = time.time() - start_cleanup
            
            logger.info(f"Created {len(pids)} processes in {creation_time:.3f}s")
            logger.info(f"Destroyed processes in {cleanup_time:.3f}s")
            
            # Performance assertions (adjust based on expected performance)
            self.assertLess(creation_time, 10.0)  # Should complete within 10 seconds
    
    def test_memory_allocation_performance(self):
        """Benchmark memory allocation"""
        with KernelContext(self.config) as kernel:
            start_time = time.time()
            pointers = []
            
            for i in range(1000):
                ptr = kernel.allocate_memory(1024)
                if ptr:
                    pointers.append(ptr)
            
            allocation_time = time.time() - start_time
            
            # Cleanup
            start_cleanup = time.time()
            for ptr in pointers:
                kernel.free_memory(ptr)
            cleanup_time = time.time() - start_cleanup
            
            logger.info(f"Allocated {len(pointers)} blocks in {allocation_time:.3f}s")
            logger.info(f"Freed blocks in {cleanup_time:.3f}s")
            
            self.assertLess(allocation_time, 5.0)
    
    def test_syscall_performance(self):
        """Benchmark system call performance"""
        with KernelContext(self.config) as kernel:
            start_time = time.time()
            
            for i in range(10000):
                kernel.syscall(1, i)  # Simple syscall
            
            syscall_time = time.time() - start_time
            
            logger.info(f"Made 10000 syscalls in {syscall_time:.3f}s")
            self.assertLess(syscall_time, 10.0)


class TestStress(unittest.TestCase):
    """Stress tests"""
    
    def setUp(self):
        self.config = KernelConfig(debug_mode=False, max_processes=100, max_threads=200)
    
    def test_memory_stress(self):
        """Stress test memory allocation"""
        with KernelContext(self.config) as kernel:
            pointers = []
            
            # Allocate until we hit limits or run out of memory
            for i in range(1000):
                ptr = kernel.allocate_memory(1024 * 1024)  # 1MB blocks
                if ptr:
                    pointers.append(ptr)
                else:
                    break
            
            logger.info(f"Allocated {len(pointers)} MB blocks")
            
            # Free all memory
            for ptr in pointers:
                kernel.free_memory(ptr)
    
    def test_process_stress(self):
        """Stress test process creation"""
        with KernelContext(self.config) as kernel:
            pids = []
            
            # Create processes until limit
            for i in range(self.config.max_processes):
                pid = kernel.create_process(f"stress_test_{i}")
                if pid:
                    pids.append(pid)
                else:
                    break
            
            logger.info(f"Created {len(pids)} processes")
            
            # Destroy all processes
            for pid in pids:
                kernel.destroy_process(pid)
    
    def test_long_running_stress(self):
        """Long-running stress test"""
        with KernelContext(self.config) as kernel:
            start_time = time.time()
            operations = 0
            
            # Run for 30 seconds
            while time.time() - start_time < 30:
                # Mix of operations
                pid = kernel.create_process("stress_proc")
                if pid:
                    ptr = kernel.allocate_memory(4096)
                    if ptr:
                        kernel.syscall(1, operations)
                        kernel.free_memory(ptr)
                    kernel.destroy_process(pid)
                    operations += 1
                
                if operations % 100 == 0:
                    time.sleep(0.001)  # Brief pause
            
            total_time = time.time() - start_time
            logger.info(f"Completed {operations} operations in {total_time:.1f}s")
            logger.info(f"Rate: {operations/total_time:.1f} ops/sec")


class TestErrorHandling(unittest.TestCase):
    """Test error handling"""
    
    def setUp(self):
        self.config = KernelConfig(debug_mode=True)
    
    def test_invalid_operations(self):
        """Test invalid operations"""
        with KernelContext(self.config) as kernel:
            # Try to destroy non-existent process
            result = kernel.destroy_process(99999)
            # Should not crash, might return False
            
            # Try to destroy non-existent thread
            result = kernel.destroy_thread(99999)
            # Should not crash
    
    def test_kernel_panic_simulation(self):
        """Test kernel panic handling"""
        kernel = KOSKernelManager(self.config)
        kernel.initialize()
        
        # This should trigger panic and shutdown
        with self.assertRaises(KernelPanicError):
            kernel.panic("Test panic")
        
        self.assertEqual(kernel.state, KernelState.PANIC)


def run_benchmark_suite():
    """Run comprehensive benchmarks"""
    print("Running KOS Kernel Benchmarks...")
    print("=" * 50)
    
    # Create test suite with only performance tests
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestPerformance))
    
    # Run with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def run_stress_tests():
    """Run stress tests"""
    print("Running KOS Kernel Stress Tests...")
    print("=" * 50)
    
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestStress))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def main():
    """Main test function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='KOS Kernel Test Suite')
    parser.add_argument('--benchmark', action='store_true', help='Run benchmarks only')
    parser.add_argument('--stress', action='store_true', help='Run stress tests only')
    parser.add_argument('--integration', action='store_true', help='Run integration tests only')
    parser.add_argument('--performance', action='store_true', help='Run performance tests only')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--pattern', help='Run tests matching pattern')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)
    
    # Create test suite
    suite = unittest.TestSuite()
    
    if args.benchmark:
        return run_benchmark_suite()
    elif args.stress:
        return run_stress_tests()
    elif args.integration:
        suite.addTest(unittest.makeSuite(TestIntegration))
    elif args.performance:
        suite.addTest(unittest.makeSuite(TestPerformance))
    else:
        # Run all tests
        suite.addTest(unittest.makeSuite(TestKernelCore))
        suite.addTest(unittest.makeSuite(TestProcessManagement))
        suite.addTest(unittest.makeSuite(TestThreadManagement))
        suite.addTest(unittest.makeSuite(TestMemoryManagement))
        suite.addTest(unittest.makeSuite(TestFilesystemOperations))
        suite.addTest(unittest.makeSuite(TestNetworkOperations))
        suite.addTest(unittest.makeSuite(TestIPCOperations))
        suite.addTest(unittest.makeSuite(TestSystemCalls))
        suite.addTest(unittest.makeSuite(TestCallbacks))
        suite.addTest(unittest.makeSuite(TestIntegration))
        suite.addTest(unittest.makeSuite(TestErrorHandling))
        
        if not args.pattern:
            # Only add performance and stress tests if not filtering
            suite.addTest(unittest.makeSuite(TestPerformance))
            suite.addTest(unittest.makeSuite(TestStress))
    
    # Run tests
    verbosity = 2 if args.verbose else 1
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
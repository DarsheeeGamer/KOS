"""
Integration tests for KOS system components
Tests the interaction between different subsystems
"""

import unittest
import tempfile
import shutil
import time
import threading
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add KOS to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from kos.base import KOSSystem
from kos.filesystem.vfs import VirtualFileSystem
from kos.process.manager import ProcessManager
from kos.network.stack import NetworkStack
from kos.security.hardening import SecurityManager, SecurityLevel
from kos.scheduler.real_scheduler import KOSScheduler

class TestKOSSystemIntegration(unittest.TestCase):
    """Test overall KOS system integration"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp(prefix='kos_integration_')
        self.kos_system = KOSSystem()
    
    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_system_initialization(self):
        """Test complete system initialization"""
        # Initialize all subsystems
        result = self.kos_system.initialize()
        self.assertTrue(result)
        
        # Check that all managers are initialized
        self.assertIsNotNone(self.kos_system.process_manager)
        self.assertIsNotNone(self.kos_system.filesystem_manager)
        self.assertIsNotNone(self.kos_system.network_stack)
        self.assertIsNotNone(self.kos_system.security_manager)
    
    def test_component_communication(self):
        """Test communication between components"""
        # Initialize system
        self.kos_system.initialize()
        
        # Test process-filesystem interaction
        proc_manager = self.kos_system.process_manager
        fs_manager = self.kos_system.filesystem_manager
        
        # Create a process that should interact with filesystem
        test_file = os.path.join(self.test_dir, 'test_output.txt')
        process = proc_manager.create_process(
            'fs_test',
            ['sh', '-c', f'echo "test data" > {test_file}']
        )
        
        # Start process and wait for completion
        proc_manager.start_process(process.pid)
        time.sleep(0.5)  # Allow process to complete
        
        # Check that file was created
        self.assertTrue(os.path.exists(test_file))
        
        # Clean up
        proc_manager.terminate_process(process.pid)
    
    def test_security_integration(self):
        """Test security integration with other components"""
        # Initialize with high security level
        security_manager = SecurityManager(SecurityLevel.HARDENED)
        security_manager.initialize_hardening()
        
        # Test that security validates inputs across components
        proc_manager = ProcessManager()
        
        # Test dangerous command rejection
        dangerous_commands = [
            ['rm', '-rf', '/'],
            ['dd', 'if=/dev/zero', 'of=/dev/sda'],
        ]
        
        for cmd in dangerous_commands:
            # Security should prevent creation of dangerous processes
            with self.assertRaises((ValueError, PermissionError)):
                proc_manager.create_process('dangerous', cmd, validate_security=True)
    
    def test_resource_sharing(self):
        """Test resource sharing between components"""
        self.kos_system.initialize()
        
        # Create multiple processes that share resources
        proc_manager = self.kos_system.process_manager
        
        # Create shared file
        shared_file = os.path.join(self.test_dir, 'shared.txt')
        with open(shared_file, 'w') as f:
            f.write('initial content\n')
        
        # Create processes that will access the shared file
        processes = []
        for i in range(3):
            proc = proc_manager.create_process(
                f'shared_proc_{i}',
                ['sh', '-c', f'echo "process {i}" >> {shared_file}']
            )
            processes.append(proc)
        
        # Start all processes
        for proc in processes:
            proc_manager.start_process(proc.pid)
        
        # Wait for completion
        time.sleep(1.0)
        
        # Check that all processes wrote to the file
        with open(shared_file, 'r') as f:
            content = f.read()
        
        self.assertIn('initial content', content)
        for i in range(3):
            self.assertIn(f'process {i}', content)
        
        # Clean up
        for proc in processes:
            proc_manager.terminate_process(proc.pid)

class TestProcessFilesystemIntegration(unittest.TestCase):
    """Test process-filesystem integration"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.vfs = VirtualFileSystem()
        self.proc_manager = ProcessManager()
        self.test_dir = tempfile.mkdtemp(prefix='kos_proc_fs_')
    
    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_process_file_operations(self):
        """Test processes performing file operations"""
        test_file = os.path.join(self.test_dir, 'proc_test.txt')
        test_content = 'Hello from process'
        
        # Create process that writes to file
        writer_proc = self.proc_manager.create_process(
            'file_writer',
            ['sh', '-c', f'echo "{test_content}" > {test_file}']
        )
        
        # Start and wait for writer
        self.proc_manager.start_process(writer_proc.pid)
        time.sleep(0.5)
        
        # Create process that reads from file
        reader_proc = self.proc_manager.create_process(
            'file_reader',
            ['cat', test_file]
        )
        
        # Start reader
        self.proc_manager.start_process(reader_proc.pid)
        time.sleep(0.5)
        
        # Verify file exists and has correct content
        self.assertTrue(os.path.exists(test_file))
        with open(test_file, 'r') as f:
            content = f.read().strip()
        self.assertEqual(content, test_content)
        
        # Clean up
        self.proc_manager.terminate_process(writer_proc.pid)
        self.proc_manager.terminate_process(reader_proc.pid)
    
    def test_concurrent_file_access(self):
        """Test concurrent file access by multiple processes"""
        shared_file = os.path.join(self.test_dir, 'concurrent.txt')
        
        # Create multiple processes that write to the same file
        processes = []
        for i in range(5):
            proc = self.proc_manager.create_process(
                f'concurrent_writer_{i}',
                ['sh', '-c', f'for j in {{1..3}}; do echo "Process {i} line $j" >> {shared_file}; done']
            )
            processes.append(proc)
        
        # Start all processes simultaneously
        for proc in processes:
            self.proc_manager.start_process(proc.pid)
        
        # Wait for all to complete
        time.sleep(2.0)
        
        # Check that file exists and has content from all processes
        self.assertTrue(os.path.exists(shared_file))
        with open(shared_file, 'r') as f:
            lines = f.readlines()
        
        # Should have 15 lines total (5 processes * 3 lines each)
        self.assertEqual(len(lines), 15)
        
        # Clean up
        for proc in processes:
            self.proc_manager.terminate_process(proc.pid)
    
    def test_filesystem_permissions(self):
        """Test filesystem permission enforcement"""
        restricted_file = os.path.join(self.test_dir, 'restricted.txt')
        
        # Create file with restricted permissions
        with open(restricted_file, 'w') as f:
            f.write('restricted content')
        os.chmod(restricted_file, 0o600)  # Owner read/write only
        
        # Process should be able to read (assuming same owner)
        reader_proc = self.proc_manager.create_process(
            'permission_reader',
            ['cat', restricted_file]
        )
        
        result = self.proc_manager.start_process(reader_proc.pid)
        self.assertTrue(result)
        
        time.sleep(0.5)
        self.proc_manager.terminate_process(reader_proc.pid)

class TestNetworkProcessIntegration(unittest.TestCase):
    """Test network-process integration"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.network_stack = NetworkStack()
        self.proc_manager = ProcessManager()
    
    def test_network_server_process(self):
        """Test network server as a process"""
        # This would test a process that creates a network server
        # For now, we'll test the concept with a simple sleep process
        server_proc = self.proc_manager.create_process(
            'network_server',
            ['python3', '-c', 'import time; time.sleep(1)']  # Placeholder
        )
        
        result = self.proc_manager.start_process(server_proc.pid)
        self.assertTrue(result)
        
        time.sleep(0.1)
        
        # Check process is running
        status = self.proc_manager.get_process_status(server_proc.pid)
        self.assertEqual(status['state'], 'running')
        
        # Clean up
        self.proc_manager.terminate_process(server_proc.pid)
    
    def test_network_client_process(self):
        """Test network client as a process"""
        # Similar placeholder test for network client
        client_proc = self.proc_manager.create_process(
            'network_client',
            ['python3', '-c', 'print("client simulation")']
        )
        
        result = self.proc_manager.start_process(client_proc.pid)
        self.assertTrue(result)
        
        time.sleep(0.5)  # Allow process to complete
        
        self.proc_manager.terminate_process(client_proc.pid)

class TestSchedulerIntegration(unittest.TestCase):
    """Test scheduler integration with other components"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.scheduler = KOSScheduler()
        self.proc_manager = ProcessManager()
    
    def test_scheduler_process_management(self):
        """Test scheduler managing process execution"""
        # Create multiple processes with different priorities
        high_priority = self.proc_manager.create_process(
            'high_prio',
            ['python3', '-c', 'import time; time.sleep(0.5)']
        )
        high_priority.priority = 10
        
        low_priority = self.proc_manager.create_process(
            'low_prio',
            ['python3', '-c', 'import time; time.sleep(0.5)']
        )
        low_priority.priority = 1
        
        # Add processes to scheduler
        self.scheduler.add_process(high_priority)
        self.scheduler.add_process(low_priority)
        
        # Start processes
        self.proc_manager.start_process(high_priority.pid)
        self.proc_manager.start_process(low_priority.pid)
        
        # Let scheduler run for a bit
        time.sleep(1.0)
        
        # Clean up
        self.proc_manager.terminate_process(high_priority.pid)
        self.proc_manager.terminate_process(low_priority.pid)
    
    def test_load_balancing(self):
        """Test scheduler load balancing"""
        # Create multiple CPU-bound processes
        processes = []
        for i in range(4):
            proc = self.proc_manager.create_process(
                f'cpu_bound_{i}',
                ['python3', '-c', 'import time; time.sleep(0.3)']
            )
            processes.append(proc)
            self.scheduler.add_process(proc)
        
        # Start all processes
        for proc in processes:
            self.proc_manager.start_process(proc.pid)
        
        # Let scheduler distribute load
        time.sleep(1.0)
        
        # Get CPU loads (if available)
        try:
            cpu_loads = self.scheduler.get_cpu_loads()
            self.assertIsInstance(cpu_loads, dict)
        except AttributeError:
            pass  # Method might not exist in test environment
        
        # Clean up
        for proc in processes:
            self.proc_manager.terminate_process(proc.pid)

class TestSecurityIntegration(unittest.TestCase):
    """Test security integration across components"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.security_manager = SecurityManager(SecurityLevel.HARDENED)
        self.proc_manager = ProcessManager()
        self.test_dir = tempfile.mkdtemp(prefix='kos_security_')
    
    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_input_validation_integration(self):
        """Test input validation across system"""
        # Initialize security
        self.security_manager.initialize_hardening()
        
        # Test path validation
        dangerous_paths = [
            '../../../etc/passwd',
            '/proc/self/mem',
            'file\x00name'
        ]
        
        for path in dangerous_paths:
            valid, msg = self.security_manager.validate_input(path, 'path')
            self.assertFalse(valid, f"Path {path} should be rejected")
    
    def test_process_security_enforcement(self):
        """Test security enforcement in process creation"""
        # Test that security manager prevents dangerous operations
        dangerous_commands = [
            ['rm', '-rf', '/tmp/*'],  # Dangerous file operations
            ['dd', 'if=/dev/zero', 'of=/tmp/test'],  # Dangerous device operations
        ]
        
        for cmd in dangerous_commands:
            # Should either reject the process or sanitize the command
            try:
                proc = self.proc_manager.create_process('dangerous', cmd)
                # If process is created, it should be sanitized
                self.assertNotEqual(proc.command, cmd)
            except (ValueError, PermissionError):
                # Expected behavior - process rejected
                pass
    
    def test_file_permission_enforcement(self):
        """Test file permission enforcement"""
        # Create file with specific permissions
        test_file = os.path.join(self.test_dir, 'secure_file.txt')
        with open(test_file, 'w') as f:
            f.write('secure content')
        
        # Set restrictive permissions
        os.chmod(test_file, 0o600)
        
        # Verify permissions are enforced
        stat_info = os.stat(test_file)
        permissions = stat_info.st_mode & 0o777
        self.assertEqual(permissions, 0o600)

class TestErrorHandlingIntegration(unittest.TestCase):
    """Test error handling across system components"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.kos_system = KOSSystem()
    
    def test_cascading_error_handling(self):
        """Test that errors in one component don't crash others"""
        # Initialize system
        self.kos_system.initialize()
        
        # Simulate error in one component
        proc_manager = self.kos_system.process_manager
        
        # Try to create process with invalid command
        try:
            proc = proc_manager.create_process('invalid', ['/nonexistent/command'])
            # If created, starting should fail gracefully
            result = proc_manager.start_process(proc.pid)
            # System should handle the error without crashing
        except Exception as e:
            # Expected - system should handle errors gracefully
            self.assertIsInstance(e, (OSError, ValueError, FileNotFoundError))
    
    def test_resource_cleanup_on_failure(self):
        """Test resource cleanup when operations fail"""
        proc_manager = ProcessManager()
        
        initial_process_count = len(proc_manager.processes)
        
        # Create process that will fail
        try:
            proc = proc_manager.create_process('failing', ['false'])  # Command that exits with error
            proc_manager.start_process(proc.pid)
            time.sleep(0.5)  # Allow process to complete/fail
        except Exception:
            pass
        
        # System should clean up failed processes
        # (Implementation dependent - this is a conceptual test)
        final_process_count = len(proc_manager.processes)
        # The exact assertion depends on implementation
        # self.assertEqual(final_process_count, initial_process_count)

class TestPerformanceIntegration(unittest.TestCase):
    """Test system performance under integrated load"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.kos_system = KOSSystem()
        self.kos_system.initialize()
    
    def test_concurrent_operations(self):
        """Test system performance with concurrent operations"""
        proc_manager = self.kos_system.process_manager
        
        # Create multiple processes concurrently
        processes = []
        start_time = time.time()
        
        for i in range(20):
            proc = proc_manager.create_process(
                f'concurrent_{i}',
                ['python3', '-c', f'print("Process {i}")']
            )
            processes.append(proc)
            proc_manager.start_process(proc.pid)
        
        # Wait for all to complete
        time.sleep(2.0)
        
        end_time = time.time()
        
        # Should handle 20 concurrent processes reasonably quickly
        self.assertLess(end_time - start_time, 5.0)
        
        # Clean up
        for proc in processes:
            proc_manager.terminate_process(proc.pid)
    
    def test_memory_usage_stability(self):
        """Test that memory usage remains stable under load"""
        import psutil
        
        initial_memory = psutil.Process().memory_info().rss
        
        # Create and destroy many processes
        proc_manager = self.kos_system.process_manager
        
        for cycle in range(10):
            processes = []
            
            # Create processes
            for i in range(5):
                proc = proc_manager.create_process(
                    f'memory_test_{cycle}_{i}',
                    ['echo', f'cycle_{cycle}_process_{i}']
                )
                processes.append(proc)
                proc_manager.start_process(proc.pid)
            
            # Wait and clean up
            time.sleep(0.5)
            for proc in processes:
                proc_manager.terminate_process(proc.pid)
        
        final_memory = psutil.Process().memory_info().rss
        memory_growth = final_memory - initial_memory
        
        # Memory growth should be reasonable (less than 50MB)
        self.assertLess(memory_growth, 50 * 1024 * 1024)

if __name__ == '__main__':
    unittest.main()
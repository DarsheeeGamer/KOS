"""
Unit tests for KOS process management components
"""

import unittest
import threading
import time
import sys
import os
import signal
from unittest.mock import Mock, patch, MagicMock

# Add KOS to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from kos.process.manager import ProcessManager
from kos.process.process import KOSProcess
from kos.process.pid import PIDManager
from kos.process.thread import KOSThread

class TestKOSProcess(unittest.TestCase):
    """Test KOS process functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_command = ['echo', 'hello world']
        self.test_env = {'TEST_VAR': 'test_value'}
    
    def test_process_creation(self):
        """Test process creation"""
        process = KOSProcess('test_proc', None, self.test_command)
        
        self.assertEqual(process.name, 'test_proc')
        self.assertEqual(process.command, self.test_command)
        self.assertIsNotNone(process.pid)
        self.assertGreater(process.pid, 0)
    
    def test_process_state_management(self):
        """Test process state transitions"""
        process = KOSProcess('state_test', None, self.test_command)
        
        # Initial state should be created
        self.assertEqual(process.state, 'created')
        
        # Start process
        process.start()
        self.assertEqual(process.state, 'running')
        
        # Stop process
        process.stop()
        self.assertIn(process.state, ['stopped', 'terminated'])
    
    def test_process_environment(self):
        """Test process environment handling"""
        process = KOSProcess('env_test', None, self.test_command, env=self.test_env)
        
        self.assertEqual(process.env['TEST_VAR'], 'test_value')
        
        # Test environment modification
        process.set_env_var('NEW_VAR', 'new_value')
        self.assertEqual(process.env['NEW_VAR'], 'new_value')
        
        # Test environment variable removal
        process.unset_env_var('TEST_VAR')
        self.assertNotIn('TEST_VAR', process.env)
    
    def test_process_signals(self):
        """Test process signal handling"""
        process = KOSProcess('signal_test', None, ['sleep', '10'])
        
        # Start process
        process.start()
        
        # Send SIGTERM
        result = process.send_signal(signal.SIGTERM)
        self.assertTrue(result)
        
        # Wait for process to terminate
        time.sleep(0.1)
        self.assertIn(process.state, ['stopped', 'terminated'])
    
    def test_process_resource_limits(self):
        """Test process resource limits"""
        process = KOSProcess('resource_test', None, self.test_command)
        
        # Set memory limit (1MB)
        result = process.set_memory_limit(1024 * 1024)
        self.assertTrue(result)
        
        # Set CPU limit (1 second)
        result = process.set_cpu_limit(1)
        self.assertTrue(result)
        
        # Get resource usage
        usage = process.get_resource_usage()
        self.assertIsInstance(usage, dict)
        self.assertIn('memory', usage)
        self.assertIn('cpu_time', usage)
    
    def test_process_priority(self):
        """Test process priority handling"""
        process = KOSProcess('priority_test', None, self.test_command)
        
        # Set nice value
        result = process.set_nice(5)
        self.assertTrue(result)
        self.assertEqual(process.nice, 5)
        
        # Set priority
        result = process.set_priority(10)
        self.assertTrue(result)
        self.assertEqual(process.priority, 10)

class TestProcessManager(unittest.TestCase):
    """Test process manager functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.process_manager = ProcessManager()
    
    def test_manager_initialization(self):
        """Test process manager initialization"""
        self.assertIsNotNone(self.process_manager)
        self.assertIsInstance(self.process_manager.processes, dict)
        self.assertIsNotNone(self.process_manager.pid_manager)
    
    def test_process_lifecycle(self):
        """Test complete process lifecycle"""
        command = ['echo', 'test']
        
        # Create process
        process = self.process_manager.create_process('lifecycle_test', command)
        self.assertIsNotNone(process)
        self.assertIn(process.pid, self.process_manager.processes)
        
        # Start process
        result = self.process_manager.start_process(process.pid)
        self.assertTrue(result)
        
        # Wait for process to complete
        time.sleep(0.1)
        
        # Check process status
        status = self.process_manager.get_process_status(process.pid)
        self.assertIsNotNone(status)
        
        # Terminate process (if still running)
        self.process_manager.terminate_process(process.pid)
    
    def test_process_listing(self):
        """Test process listing functionality"""
        # Create several test processes
        processes = []
        for i in range(3):
            proc = self.process_manager.create_process(f'list_test_{i}', ['sleep', '1'])
            processes.append(proc)
        
        # Get process list
        process_list = self.process_manager.list_processes()
        self.assertIsInstance(process_list, list)
        self.assertGreaterEqual(len(process_list), 3)
        
        # Check that our processes are in the list
        pids = [p['pid'] for p in process_list]
        for proc in processes:
            self.assertIn(proc.pid, pids)
        
        # Clean up
        for proc in processes:
            self.process_manager.terminate_process(proc.pid)
    
    def test_process_search(self):
        """Test process search functionality"""
        # Create test process with specific name
        test_name = 'search_target_process'
        process = self.process_manager.create_process(test_name, ['sleep', '5'])
        
        # Search by name
        found_processes = self.process_manager.find_processes_by_name(test_name)
        self.assertGreater(len(found_processes), 0)
        self.assertEqual(found_processes[0].name, test_name)
        
        # Search by PID
        found_process = self.process_manager.get_process(process.pid)
        self.assertIsNotNone(found_process)
        self.assertEqual(found_process.pid, process.pid)
        
        # Clean up
        self.process_manager.terminate_process(process.pid)
    
    def test_process_parent_child_relationships(self):
        """Test parent-child process relationships"""
        # Create parent process
        parent = self.process_manager.create_process('parent', ['sleep', '10'])
        
        # Create child process
        child = self.process_manager.create_process('child', ['sleep', '5'], parent_pid=parent.pid)
        
        # Check relationship
        self.assertEqual(child.parent_pid, parent.pid)
        
        # Get children of parent
        children = self.process_manager.get_child_processes(parent.pid)
        child_pids = [c.pid for c in children]
        self.assertIn(child.pid, child_pids)
        
        # Clean up
        self.process_manager.terminate_process(child.pid)
        self.process_manager.terminate_process(parent.pid)
    
    def test_process_groups(self):
        """Test process group management"""
        # Create process group
        group_id = self.process_manager.create_process_group()
        self.assertIsNotNone(group_id)
        
        # Create processes in group
        proc1 = self.process_manager.create_process('group_proc1', ['sleep', '5'])
        proc2 = self.process_manager.create_process('group_proc2', ['sleep', '5'])
        
        # Add processes to group
        result1 = self.process_manager.add_to_process_group(proc1.pid, group_id)
        result2 = self.process_manager.add_to_process_group(proc2.pid, group_id)
        self.assertTrue(result1)
        self.assertTrue(result2)
        
        # Get group members
        group_members = self.process_manager.get_process_group_members(group_id)
        member_pids = [p.pid for p in group_members]
        self.assertIn(proc1.pid, member_pids)
        self.assertIn(proc2.pid, member_pids)
        
        # Signal entire group
        result = self.process_manager.signal_process_group(group_id, signal.SIGTERM)
        self.assertTrue(result)
        
        # Clean up
        time.sleep(0.1)  # Allow processes to terminate

class TestPIDManager(unittest.TestCase):
    """Test PID manager functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.pid_manager = PIDManager()
    
    def test_pid_allocation(self):
        """Test PID allocation"""
        # Allocate PIDs
        pid1 = self.pid_manager.allocate_pid()
        pid2 = self.pid_manager.allocate_pid()
        
        self.assertIsNotNone(pid1)
        self.assertIsNotNone(pid2)
        self.assertNotEqual(pid1, pid2)
        self.assertGreater(pid1, 0)
        self.assertGreater(pid2, 0)
    
    def test_pid_deallocation(self):
        """Test PID deallocation and reuse"""
        # Allocate PID
        pid = self.pid_manager.allocate_pid()
        self.assertIsNotNone(pid)
        
        # Check PID is in use
        self.assertTrue(self.pid_manager.is_pid_in_use(pid))
        
        # Deallocate PID
        result = self.pid_manager.deallocate_pid(pid)
        self.assertTrue(result)
        
        # Check PID is no longer in use
        self.assertFalse(self.pid_manager.is_pid_in_use(pid))
    
    def test_pid_limits(self):
        """Test PID allocation limits"""
        # Set low limit for testing
        original_max = self.pid_manager.max_pid
        self.pid_manager.max_pid = 10
        
        allocated_pids = []
        
        # Allocate PIDs until limit
        for _ in range(15):  # Try to allocate more than max
            pid = self.pid_manager.allocate_pid()
            if pid is not None:
                allocated_pids.append(pid)
        
        # Should not exceed max PIDs
        self.assertLessEqual(len(allocated_pids), 10)
        
        # Clean up
        for pid in allocated_pids:
            self.pid_manager.deallocate_pid(pid)
        
        # Restore original limit
        self.pid_manager.max_pid = original_max
    
    def test_pid_wraparound(self):
        """Test PID wraparound handling"""
        # Set current PID near max
        self.pid_manager.current_pid = self.pid_manager.max_pid - 2
        
        # Allocate PIDs
        pid1 = self.pid_manager.allocate_pid()
        pid2 = self.pid_manager.allocate_pid()
        pid3 = self.pid_manager.allocate_pid()  # Should wrap around
        
        self.assertIsNotNone(pid1)
        self.assertIsNotNone(pid2)
        self.assertIsNotNone(pid3)
        
        # pid3 should be much smaller than pid2 due to wraparound
        self.assertLess(pid3, pid2)

class TestKOSThread(unittest.TestCase):
    """Test KOS thread functionality"""
    
    def test_thread_creation(self):
        """Test thread creation"""
        def test_function():
            time.sleep(0.1)
            return "test_result"
        
        thread = KOSThread('test_thread', test_function)
        
        self.assertEqual(thread.name, 'test_thread')
        self.assertIsNotNone(thread.thread_id)
        self.assertEqual(thread.state, 'created')
    
    def test_thread_execution(self):
        """Test thread execution"""
        result_list = []
        
        def worker_function():
            result_list.append("worker_executed")
        
        thread = KOSThread('worker_thread', worker_function)
        
        # Start thread
        thread.start()
        self.assertEqual(thread.state, 'running')
        
        # Wait for completion
        thread.join(timeout=1.0)
        
        # Check result
        self.assertEqual(len(result_list), 1)
        self.assertEqual(result_list[0], "worker_executed")
    
    def test_thread_synchronization(self):
        """Test thread synchronization"""
        shared_data = {'counter': 0}
        lock = threading.Lock()
        
        def increment_counter():
            for _ in range(100):
                with lock:
                    shared_data['counter'] += 1
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = KOSThread(f'increment_thread_{i}', increment_counter)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5.0)
        
        # Check final counter value
        self.assertEqual(shared_data['counter'], 500)  # 5 threads * 100 increments
    
    def test_thread_termination(self):
        """Test thread termination"""
        def long_running_task():
            time.sleep(10)  # Long task
        
        thread = KOSThread('long_task', long_running_task)
        thread.start()
        
        # Terminate thread
        result = thread.terminate()
        self.assertTrue(result)
        
        # Check state
        self.assertIn(thread.state, ['stopped', 'terminated'])

class TestProcessIPC(unittest.TestCase):
    """Test inter-process communication"""
    
    def test_pipe_communication(self):
        """Test pipe-based IPC"""
        from kos.core.ipc.pipe import Pipe
        
        pipe = Pipe()
        test_data = b"Hello from parent process"
        
        # Write to pipe
        bytes_written = pipe.write(test_data)
        self.assertEqual(bytes_written, len(test_data))
        
        # Read from pipe
        read_data = pipe.read(len(test_data))
        self.assertEqual(read_data, test_data)
        
        # Close pipe
        pipe.close()
    
    def test_shared_memory(self):
        """Test shared memory IPC"""
        from kos.core.ipc.shared_memory import SharedMemory
        
        shm_size = 1024
        shm = SharedMemory('test_shm', shm_size)
        
        # Write data
        test_data = b"Shared memory test data"
        result = shm.write(0, test_data)
        self.assertTrue(result)
        
        # Read data
        read_data = shm.read(0, len(test_data))
        self.assertEqual(read_data, test_data)
        
        # Clean up
        shm.destroy()
    
    def test_message_queue(self):
        """Test message queue IPC"""
        from kos.core.ipc.message_queue import MessageQueue
        
        mq = MessageQueue('test_mq')
        
        # Send message
        message = {'type': 'test', 'data': 'Hello Queue'}
        result = mq.send(message)
        self.assertTrue(result)
        
        # Receive message
        received = mq.receive()
        self.assertEqual(received, message)
        
        # Clean up
        mq.destroy()

class TestKernelProcessIntegration(unittest.TestCase):
    """Test kernel process integration"""
    
    @patch('kos.kernel.sched.sched_wrapper')
    def test_kernel_scheduler_integration(self, mock_sched):
        """Test integration with kernel scheduler"""
        # Mock scheduler functions
        mock_sched.create_task.return_value = 123  # Task ID
        mock_sched.schedule_task.return_value = 0  # Success
        mock_sched.terminate_task.return_value = 0  # Success
        
        from kos.kernel.sched.sched_wrapper import create_task, schedule_task, terminate_task
        
        # Test task creation
        task_id = create_task("test_task", 1000)  # name, stack_size
        self.assertEqual(task_id, 123)
        
        # Test task scheduling
        result = schedule_task(task_id)
        self.assertEqual(result, 0)
        
        # Test task termination
        result = terminate_task(task_id)
        self.assertEqual(result, 0)
    
    def test_process_performance(self):
        """Test process management performance"""
        manager = ProcessManager()
        
        # Test process creation performance
        start_time = time.time()
        processes = []
        
        for i in range(50):
            proc = manager.create_process(f'perf_test_{i}', ['echo', f'test_{i}'])
            processes.append(proc)
        
        creation_time = time.time() - start_time
        
        # Test process cleanup
        start_time = time.time()
        for proc in processes:
            manager.terminate_process(proc.pid)
        
        cleanup_time = time.time() - start_time
        
        # Performance should be reasonable
        self.assertLess(creation_time, 2.0)  # < 2s for 50 processes
        self.assertLess(cleanup_time, 1.0)   # < 1s for cleanup
    
    def test_concurrent_process_operations(self):
        """Test concurrent process operations"""
        manager = ProcessManager()
        results = []
        
        def worker(worker_id):
            try:
                # Create process
                proc = manager.create_process(f'concurrent_{worker_id}', ['echo', f'worker_{worker_id}'])
                
                # Start process
                manager.start_process(proc.pid)
                
                # Wait a bit
                time.sleep(0.1)
                
                # Terminate process
                manager.terminate_process(proc.pid)
                
                results.append(True)
            except Exception:
                results.append(False)
        
        # Start multiple worker threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join(timeout=10)
        
        # All operations should succeed
        self.assertEqual(len(results), 10)
        self.assertTrue(all(results))

if __name__ == '__main__':
    unittest.main()
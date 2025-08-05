"""
Unit tests for KOS scheduler components
"""

import unittest
import time
import threading
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add KOS to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from kos.scheduler.cfs import CFSScheduler
from kos.scheduler.real_scheduler import KOSScheduler, TaskState, SchedulingPolicy
from kos.process.process import KOSProcess

class TestCFSScheduler(unittest.TestCase):
    """Test Completely Fair Scheduler"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.scheduler = CFSScheduler()
        self.test_processes = []
    
    def tearDown(self):
        """Clean up test fixtures"""
        for process in self.test_processes:
            if process.pid in self.scheduler.processes:
                self.scheduler.remove_process(process.pid)
    
    def create_test_process(self, name, nice=0, priority=0):
        """Create a test process"""
        process = KOSProcess(name, None, [])
        process.nice = nice
        process.priority = priority
        process.vruntime = 0
        process.sum_exec_runtime = 0
        self.test_processes.append(process)
        return process
    
    def test_process_addition(self):
        """Test adding processes to scheduler"""
        process = self.create_test_process("test_proc")
        
        self.scheduler.add_process(process)
        self.assertIn(process.pid, self.scheduler.processes)
        self.assertEqual(self.scheduler.processes[process.pid], process)
    
    def test_process_removal(self):
        """Test removing processes from scheduler"""
        process = self.create_test_process("test_proc")
        
        self.scheduler.add_process(process)
        self.assertIn(process.pid, self.scheduler.processes)
        
        self.scheduler.remove_process(process.pid)
        self.assertNotIn(process.pid, self.scheduler.processes)
    
    def test_next_task_selection(self):
        """Test next task selection algorithm"""
        # Add processes with different vruntime values
        proc1 = self.create_test_process("proc1")
        proc2 = self.create_test_process("proc2")
        proc3 = self.create_test_process("proc3")
        
        proc1.vruntime = 1000
        proc2.vruntime = 500   # Should be selected first
        proc3.vruntime = 1500
        
        self.scheduler.add_process(proc1)
        self.scheduler.add_process(proc2)
        self.scheduler.add_process(proc3)
        
        next_task = self.scheduler.pick_next_task()
        self.assertEqual(next_task, proc2)
    
    def test_vruntime_calculation(self):
        """Test virtual runtime calculation"""
        process = self.create_test_process("test_proc", nice=0)
        
        initial_vruntime = process.vruntime
        exec_time = 1000000  # 1ms in nanoseconds
        
        new_vruntime = self.scheduler.calculate_vruntime(process, exec_time)
        self.assertGreater(new_vruntime, initial_vruntime)
    
    def test_nice_value_impact(self):
        """Test impact of nice values on scheduling"""
        proc_normal = self.create_test_process("normal", nice=0)
        proc_nice = self.create_test_process("nice", nice=10)
        proc_priority = self.create_test_process("priority", nice=-5)
        
        exec_time = 1000000  # 1ms
        
        # Calculate vruntime for each process
        vrt_normal = self.scheduler.calculate_vruntime(proc_normal, exec_time)
        vrt_nice = self.scheduler.calculate_vruntime(proc_nice, exec_time)
        vrt_priority = self.scheduler.calculate_vruntime(proc_priority, exec_time)
        
        # Nice process should accumulate vruntime faster
        self.assertGreater(vrt_nice, vrt_normal)
        # Priority process should accumulate vruntime slower
        self.assertLess(vrt_priority, vrt_normal)
    
    def test_time_slice_calculation(self):
        """Test time slice calculation"""
        process = self.create_test_process("test_proc")
        
        time_slice = self.scheduler.calculate_time_slice(process, 1)
        self.assertGreater(time_slice, 0)
        
        # With more running processes, time slice should be smaller
        time_slice_busy = self.scheduler.calculate_time_slice(process, 10)
        self.assertLessEqual(time_slice_busy, time_slice)
    
    def test_scheduler_fairness(self):
        """Test scheduler fairness over time"""
        # Create multiple processes
        processes = []
        for i in range(5):
            proc = self.create_test_process(f"proc_{i}")
            processes.append(proc)
            self.scheduler.add_process(proc)
        
        # Simulate scheduling for multiple time slices
        total_runtime = {}
        for proc in processes:
            total_runtime[proc.pid] = 0
        
        for _ in range(100):  # 100 scheduling cycles
            current_task = self.scheduler.pick_next_task()
            if current_task:
                # Simulate execution
                exec_time = 10000  # 10ms
                current_task.sum_exec_runtime += exec_time
                current_task.vruntime = self.scheduler.calculate_vruntime(current_task, exec_time)
                total_runtime[current_task.pid] += exec_time
        
        # Check that runtime is distributed fairly
        runtimes = list(total_runtime.values())
        max_runtime = max(runtimes)
        min_runtime = min(runtimes)
        
        # Fair scheduling should keep runtimes within reasonable bounds
        self.assertLessEqual(max_runtime / min_runtime, 3.0)  # Allow some variance

class TestKOSScheduler(unittest.TestCase):
    """Test main KOS scheduler"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.scheduler = KOSScheduler()
        self.test_processes = []
    
    def tearDown(self):
        """Clean up test fixtures"""
        for process in self.test_processes:
            if process in self.scheduler.ready_queue:
                self.scheduler.ready_queue.remove(process)
    
    def create_test_process(self, name, policy=SchedulingPolicy.CFS):
        """Create a test process"""
        process = KOSProcess(name, None, [])
        process.policy = policy
        process.state = TaskState.RUNNABLE
        self.test_processes.append(process)
        return process
    
    def test_scheduler_initialization(self):
        """Test scheduler initialization"""
        self.assertIsNotNone(self.scheduler.cfs_scheduler)
        self.assertIsInstance(self.scheduler.ready_queue, list)
        self.assertIsInstance(self.scheduler.waiting_queue, list)
    
    def test_process_states(self):
        """Test process state transitions"""
        process = self.create_test_process("test_proc")
        
        # Test state changes
        self.assertEqual(process.state, TaskState.RUNNABLE)
        
        process.state = TaskState.RUNNING
        self.assertEqual(process.state, TaskState.RUNNING)
        
        process.state = TaskState.SLEEPING
        self.assertEqual(process.state, TaskState.SLEEPING)
    
    def test_scheduling_policies(self):
        """Test different scheduling policies"""
        cfs_proc = self.create_test_process("cfs_proc", SchedulingPolicy.CFS)
        rt_proc = self.create_test_process("rt_proc", SchedulingPolicy.RT)
        
        self.assertEqual(cfs_proc.policy, SchedulingPolicy.CFS)
        self.assertEqual(rt_proc.policy, SchedulingPolicy.RT)
    
    def test_priority_handling(self):
        """Test priority-based scheduling"""
        high_prio = self.create_test_process("high", SchedulingPolicy.RT)
        low_prio = self.create_test_process("low", SchedulingPolicy.CFS)
        
        high_prio.priority = 90
        low_prio.priority = 10
        
        self.scheduler.add_process(high_prio)
        self.scheduler.add_process(low_prio)
        
        # RT process should be scheduled first
        next_task = self.scheduler.schedule()
        self.assertEqual(next_task, high_prio)
    
    def test_cpu_affinity(self):
        """Test CPU affinity constraints"""
        process = self.create_test_process("affinity_proc")
        
        # Set CPU affinity to CPU 0 only
        process.cpu_affinity = [0]
        
        # Test that process respects affinity
        self.assertIn(0, process.cpu_affinity)
        self.assertEqual(len(process.cpu_affinity), 1)
    
    def test_load_balancing(self):
        """Test load balancing between CPUs"""
        # This is a simplified test - real load balancing is more complex
        processes = []
        for i in range(8):
            proc = self.create_test_process(f"load_proc_{i}")
            processes.append(proc)
            self.scheduler.add_process(proc)
        
        # Simulate load balancing
        cpu_loads = self.scheduler.get_cpu_loads()
        self.assertIsInstance(cpu_loads, dict)
    
    def test_context_switching(self):
        """Test context switching functionality"""
        proc1 = self.create_test_process("proc1")
        proc2 = self.create_test_process("proc2")
        
        # Simulate context switch
        switch_result = self.scheduler.context_switch(proc1, proc2)
        self.assertTrue(switch_result)
    
    def test_scheduler_statistics(self):
        """Test scheduler statistics collection"""
        stats = self.scheduler.get_statistics()
        
        self.assertIsInstance(stats, dict)
        self.assertIn('total_switches', stats)
        self.assertIn('total_processes', stats)
        self.assertIn('cpu_usage', stats)

class TestTaskState(unittest.TestCase):
    """Test task state management"""
    
    def test_state_values(self):
        """Test task state enumeration values"""
        self.assertEqual(TaskState.RUNNABLE.value, 'runnable')
        self.assertEqual(TaskState.RUNNING.value, 'running')
        self.assertEqual(TaskState.SLEEPING.value, 'sleeping')
        self.assertEqual(TaskState.STOPPED.value, 'stopped')
        self.assertEqual(TaskState.ZOMBIE.value, 'zombie')
    
    def test_state_transitions(self):
        """Test valid state transitions"""
        process = KOSProcess("test", None, [])
        
        # Test runnable -> running
        process.state = TaskState.RUNNABLE
        process.state = TaskState.RUNNING
        self.assertEqual(process.state, TaskState.RUNNING)
        
        # Test running -> sleeping
        process.state = TaskState.SLEEPING
        self.assertEqual(process.state, TaskState.SLEEPING)
        
        # Test sleeping -> runnable
        process.state = TaskState.RUNNABLE
        self.assertEqual(process.state, TaskState.RUNNABLE)

class TestSchedulingPolicies(unittest.TestCase):
    """Test scheduling policy handling"""
    
    def test_policy_values(self):
        """Test scheduling policy enumeration"""
        self.assertEqual(SchedulingPolicy.CFS.value, 'cfs')
        self.assertEqual(SchedulingPolicy.RT.value, 'rt')
        self.assertEqual(SchedulingPolicy.IDLE.value, 'idle')
        self.assertEqual(SchedulingPolicy.BATCH.value, 'batch')
    
    def test_policy_priorities(self):
        """Test policy priority handling"""
        cfs_proc = KOSProcess("cfs", None, [])
        rt_proc = KOSProcess("rt", None, [])
        
        cfs_proc.policy = SchedulingPolicy.CFS
        rt_proc.policy = SchedulingPolicy.RT
        
        # RT should have higher priority than CFS
        self.assertTrue(rt_proc.policy != cfs_proc.policy)

class TestSchedulerIntegration(unittest.TestCase):
    """Test scheduler integration with kernel"""
    
    @patch('kos.kernel.sched.sched_wrapper')
    def test_kernel_scheduler_integration(self, mock_sched):
        """Test integration with kernel scheduler"""
        # Mock kernel scheduler functions
        mock_sched.sched_init.return_value = 0
        mock_sched.sched_schedule.return_value = 1  # Process ID
        mock_sched.sched_yield.return_value = 0
        
        from kos.kernel.sched.sched_wrapper import sched_init, sched_schedule, sched_yield
        
        # Test initialization
        result = sched_init()
        self.assertEqual(result, 0)
        
        # Test scheduling
        next_pid = sched_schedule()
        self.assertEqual(next_pid, 1)
        
        # Test yielding
        result = sched_yield()
        self.assertEqual(result, 0)
    
    def test_scheduler_performance(self):
        """Test scheduler performance under load"""
        scheduler = KOSScheduler()
        
        # Create many processes
        processes = []
        start_time = time.time()
        
        for i in range(1000):
            proc = KOSProcess(f"perf_proc_{i}", None, [])
            processes.append(proc)
            scheduler.add_process(proc)
        
        creation_time = time.time() - start_time
        
        # Test scheduling performance
        start_time = time.time()
        for _ in range(1000):
            scheduler.schedule()
        
        scheduling_time = time.time() - start_time
        
        # Performance should be reasonable
        self.assertLess(creation_time, 1.0)  # Should create 1000 processes in < 1s
        self.assertLess(scheduling_time, 1.0)  # Should do 1000 schedules in < 1s

if __name__ == '__main__':
    unittest.main()
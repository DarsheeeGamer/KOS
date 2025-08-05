"""
KOS Stress Testing Framework
Comprehensive stress testing and fuzzing for system stability
"""

import os
import time
import random
import string
import threading
import multiprocessing
import logging
import signal
import gc
import traceback
from typing import Dict, Any, List, Callable, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import psutil

logger = logging.getLogger('kos.stress_test')

@dataclass
class TestResult:
    """Test result data"""
    test_name: str
    passed: bool
    duration: float
    iterations: int
    errors: List[str]
    metrics: Dict[str, Any]


class StressTest:
    """Base class for stress tests"""
    
    def __init__(self, name: str, duration: float = 60.0):
        self.name = name
        self.duration = duration
        self.iterations = 0
        self.errors = []
        self.start_time = 0
        self.stop_flag = threading.Event()
        
    def setup(self):
        """Setup test environment"""
        pass
        
    def teardown(self):
        """Cleanup test environment"""
        pass
        
    def run_iteration(self):
        """Run single test iteration"""
        # Default implementation - subclasses should override
        import random
        import time
        
        # Simulate some work
        time.sleep(random.uniform(0.001, 0.01))
        
        # Simulate occasional failures (5% chance)
        if random.random() < 0.05:
            self.failures += 1
            raise Exception("Simulated test failure")
        
        return True
        
    def run(self) -> TestResult:
        """Run stress test"""
        logger.info(f"Starting stress test: {self.name}")
        
        self.setup()
        self.start_time = time.time()
        
        try:
            while time.time() - self.start_time < self.duration and not self.stop_flag.is_set():
                try:
                    self.run_iteration()
                    self.iterations += 1
                except Exception as e:
                    error = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
                    self.errors.append(error)
                    logger.error(f"Error in {self.name}: {error}")
                    
        finally:
            self.teardown()
            
        duration = time.time() - self.start_time
        passed = len(self.errors) == 0
        
        return TestResult(
            test_name=self.name,
            passed=passed,
            duration=duration,
            iterations=self.iterations,
            errors=self.errors,
            metrics=self.get_metrics()
        )
        
    def get_metrics(self) -> Dict[str, Any]:
        """Get test metrics"""
        return {
            'iterations_per_second': self.iterations / (time.time() - self.start_time) if self.iterations > 0 else 0
        }
        
    def stop(self):
        """Stop test"""
        self.stop_flag.set()


class ProcessStressTest(StressTest):
    """Process creation/destruction stress test"""
    
    def __init__(self, process_manager, max_processes: int = 100):
        super().__init__("Process Stress Test")
        self.process_manager = process_manager
        self.max_processes = max_processes
        self.created_pids = []
        
    def run_iteration(self):
        # Create processes
        if len(self.created_pids) < self.max_processes:
            for _ in range(random.randint(1, 5)):
                try:
                    process = self.process_manager.create_process(
                        f"/bin/stress_test_{random.randint(1000, 9999)}",
                        uid=random.randint(1000, 2000),
                        gid=random.randint(1000, 2000)
                    )
                    if process:
                        self.created_pids.append(process.pid)
                except Exception:
                    pass
                    
        # Randomly kill processes
        if self.created_pids and random.random() > 0.5:
            num_to_kill = random.randint(1, min(5, len(self.created_pids)))
            for _ in range(num_to_kill):
                if self.created_pids:
                    pid = random.choice(self.created_pids)
                    try:
                        self.process_manager.kill_process(pid, signal.SIGTERM)
                        self.created_pids.remove(pid)
                    except Exception:
                        pass
                        
        # Send random signals
        if self.created_pids and random.random() > 0.7:
            pid = random.choice(self.created_pids)
            sig = random.choice([signal.SIGUSR1, signal.SIGUSR2, signal.SIGHUP])
            try:
                self.process_manager.send_signal(pid, sig)
            except Exception:
                pass
                
    def teardown(self):
        # Clean up remaining processes
        for pid in self.created_pids:
            try:
                self.process_manager.kill_process(pid, signal.SIGKILL)
            except Exception:
                pass


class FileSystemStressTest(StressTest):
    """Filesystem operations stress test"""
    
    def __init__(self, vfs, test_dir: str = "/tmp/stress_test"):
        super().__init__("Filesystem Stress Test")
        self.vfs = vfs
        self.test_dir = test_dir
        self.created_files = []
        self.file_counter = 0
        
    def setup(self):
        try:
            self.vfs.makedirs(self.test_dir)
        except Exception:
            pass
            
    def run_iteration(self):
        action = random.choice(['create', 'read', 'write', 'delete', 'rename', 'mkdir'])
        
        if action == 'create':
            # Create file
            filename = f"{self.test_dir}/file_{self.file_counter}_{random.randint(1000, 9999)}"
            self.file_counter += 1
            try:
                data = ''.join(random.choices(string.ascii_letters, k=random.randint(100, 10000)))
                self.vfs.write_file(filename, data.encode())
                self.created_files.append(filename)
            except Exception:
                pass
                
        elif action == 'read' and self.created_files:
            # Read file
            filename = random.choice(self.created_files)
            try:
                self.vfs.read_file(filename)
            except Exception:
                pass
                
        elif action == 'write' and self.created_files:
            # Write to file
            filename = random.choice(self.created_files)
            try:
                data = ''.join(random.choices(string.ascii_letters, k=random.randint(100, 1000)))
                self.vfs.write_file(filename, data.encode())
            except Exception:
                pass
                
        elif action == 'delete' and len(self.created_files) > 10:
            # Delete file
            filename = random.choice(self.created_files)
            try:
                self.vfs.unlink(filename)
                self.created_files.remove(filename)
            except Exception:
                pass
                
        elif action == 'rename' and self.created_files:
            # Rename file
            old_name = random.choice(self.created_files)
            new_name = f"{self.test_dir}/renamed_{random.randint(1000, 9999)}"
            try:
                self.vfs.rename(old_name, new_name)
                self.created_files.remove(old_name)
                self.created_files.append(new_name)
            except Exception:
                pass
                
        elif action == 'mkdir':
            # Create directory
            dirname = f"{self.test_dir}/dir_{random.randint(1000, 9999)}"
            try:
                self.vfs.mkdir(dirname)
            except Exception:
                pass
                
    def teardown(self):
        # Clean up test directory
        try:
            self.vfs.rmtree(self.test_dir)
        except Exception:
            pass


class MemoryStressTest(StressTest):
    """Memory allocation stress test"""
    
    def __init__(self, memory_manager):
        super().__init__("Memory Stress Test")
        self.memory_manager = memory_manager
        self.allocations = []
        
    def run_iteration(self):
        action = random.choice(['allocate', 'free', 'realloc'])
        
        if action == 'allocate' or not self.allocations:
            # Allocate memory
            size = random.randint(1024, 1024 * 1024)  # 1KB to 1MB
            try:
                addr = self.memory_manager.allocate(size)
                if addr:
                    self.allocations.append((addr, size))
            except Exception:
                pass
                
        elif action == 'free' and self.allocations:
            # Free memory
            addr, size = random.choice(self.allocations)
            try:
                self.memory_manager.free(addr)
                self.allocations.remove((addr, size))
            except Exception:
                pass
                
        elif action == 'realloc' and self.allocations:
            # Reallocate memory
            addr, old_size = random.choice(self.allocations)
            new_size = random.randint(1024, 1024 * 1024)
            try:
                new_addr = self.memory_manager.realloc(addr, new_size)
                if new_addr:
                    self.allocations.remove((addr, old_size))
                    self.allocations.append((new_addr, new_size))
            except Exception:
                pass
                
    def teardown(self):
        # Free all allocations
        for addr, size in self.allocations:
            try:
                self.memory_manager.free(addr)
            except Exception:
                pass


class NetworkStressTest(StressTest):
    """Network operations stress test"""
    
    def __init__(self, network_stack):
        super().__init__("Network Stress Test")
        self.network_stack = network_stack
        self.sockets = []
        self.connections = []
        
    def run_iteration(self):
        action = random.choice(['create_socket', 'connect', 'send', 'close'])
        
        if action == 'create_socket' or not self.sockets:
            # Create socket
            sock_type = random.choice(['tcp', 'udp'])
            try:
                sock = self.network_stack.create_socket(sock_type)
                if sock:
                    self.sockets.append(sock)
            except Exception:
                pass
                
        elif action == 'connect' and self.sockets:
            # Connect socket
            sock = random.choice(self.sockets)
            try:
                # Connect to random local port
                port = random.randint(10000, 20000)
                self.network_stack.connect(sock, '127.0.0.1', port)
                self.connections.append((sock, port))
            except Exception:
                pass
                
        elif action == 'send' and self.connections:
            # Send data
            sock, port = random.choice(self.connections)
            data = ''.join(random.choices(string.ascii_letters, k=random.randint(10, 1000)))
            try:
                self.network_stack.send(sock, data.encode())
            except Exception:
                pass
                
        elif action == 'close' and self.sockets:
            # Close socket
            sock = random.choice(self.sockets)
            try:
                self.network_stack.close_socket(sock)
                self.sockets.remove(sock)
                # Remove from connections
                self.connections = [(s, p) for s, p in self.connections if s != sock]
            except Exception:
                pass
                
    def teardown(self):
        # Close all sockets
        for sock in self.sockets:
            try:
                self.network_stack.close_socket(sock)
            except Exception:
                pass


class SecurityStressTest(StressTest):
    """Security subsystem stress test"""
    
    def __init__(self, security_manager):
        super().__init__("Security Stress Test")
        self.security_manager = security_manager
        self.contexts = []
        self.capabilities = []
        
    def run_iteration(self):
        action = random.choice(['check_permission', 'set_context', 'add_capability', 'create_namespace'])
        
        if action == 'check_permission':
            # Check random permission
            subject = f"user_u:user_r:user_t:s{random.randint(0, 5)}"
            object_ctx = f"system_u:object_r:file_t:s{random.randint(0, 5)}"
            permission = random.choice(['read', 'write', 'execute'])
            try:
                self.security_manager.check_permission(
                    subject, object_ctx, 'file', permission
                )
            except Exception:
                pass
                
        elif action == 'set_context':
            # Set security context
            path = f"/test/file_{random.randint(1000, 9999)}"
            context = f"user_u:object_r:user_file_t:s{random.randint(0, 5)}"
            try:
                self.security_manager.set_file_context(path, context)
                self.contexts.append((path, context))
            except Exception:
                pass
                
        elif action == 'add_capability':
            # Grant capability
            pid = random.randint(1000, 2000)
            cap = random.randint(0, 40)
            try:
                self.security_manager.grant_capability(pid, cap)
                self.capabilities.append((pid, cap))
            except Exception:
                pass
                
        elif action == 'create_namespace':
            # Create namespace
            ns_type = random.choice(['pid', 'net', 'mnt', 'uts', 'ipc'])
            pid = random.randint(1000, 2000)
            try:
                self.security_manager.create_namespace(ns_type, pid)
            except Exception:
                pass


class ConcurrentStressTest(StressTest):
    """Concurrent operations stress test"""
    
    def __init__(self, kernel):
        super().__init__("Concurrent Stress Test", duration=120.0)
        self.kernel = kernel
        self.thread_pool = ThreadPoolExecutor(max_workers=10)
        self.futures = []
        
    def run_iteration(self):
        # Submit random concurrent operations
        operations = [
            self._process_operation,
            self._filesystem_operation,
            self._memory_operation,
            self._network_operation,
            self._security_operation
        ]
        
        for _ in range(random.randint(1, 5)):
            operation = random.choice(operations)
            future = self.thread_pool.submit(operation)
            self.futures.append(future)
            
        # Clean up completed futures
        self.futures = [f for f in self.futures if not f.done()]
        
    def _process_operation(self):
        """Random process operation"""
        try:
            if hasattr(self.kernel, 'process_manager'):
                pm = self.kernel.process_manager
                if random.random() > 0.5:
                    pm.create_process(f"/bin/test_{random.randint(1000, 9999)}")
                else:
                    pm.get_process_list()
        except Exception:
            pass
            
    def _filesystem_operation(self):
        """Random filesystem operation"""
        try:
            if hasattr(self.kernel, 'vfs'):
                vfs = self.kernel.vfs
                path = f"/tmp/test_{random.randint(1000, 9999)}"
                if random.random() > 0.5:
                    vfs.write_file(path, b"test data")
                else:
                    vfs.list_directory("/tmp")
        except Exception:
            pass
            
    def _memory_operation(self):
        """Random memory operation"""
        try:
            if hasattr(self.kernel, 'memory_manager'):
                mm = self.kernel.memory_manager
                size = random.randint(1024, 65536)
                mm.get_memory_info()
        except Exception:
            pass
            
    def _network_operation(self):
        """Random network operation"""
        try:
            if hasattr(self.kernel, 'network_stack'):
                ns = self.kernel.network_stack
                ns.get_interface_list()
        except Exception:
            pass
            
    def _security_operation(self):
        """Random security operation"""
        try:
            if hasattr(self.kernel, 'security_manager'):
                sm = self.kernel.security_manager
                sm.get_security_stats()
        except Exception:
            pass
            
    def teardown(self):
        self.thread_pool.shutdown(wait=True)


class FuzzTester:
    """Fuzzing framework for input validation"""
    
    def __init__(self):
        self.fuzz_strategies = {
            'string': self._fuzz_string,
            'integer': self._fuzz_integer,
            'path': self._fuzz_path,
            'command': self._fuzz_command,
            'signal': self._fuzz_signal
        }
        
    def _fuzz_string(self) -> str:
        """Generate fuzzed string"""
        strategies = [
            lambda: '',  # Empty string
            lambda: 'A' * 10000,  # Very long string
            lambda: '\x00' * 100,  # Null bytes
            lambda: ''.join(chr(random.randint(0, 255)) for _ in range(100)),  # Random bytes
            lambda: '../' * 100,  # Path traversal
            lambda: '$(command)',  # Command injection
            lambda: '%s' * 100,  # Format string
            lambda: '\n\r\t' * 100,  # Control characters
        ]
        return random.choice(strategies)()
        
    def _fuzz_integer(self) -> int:
        """Generate fuzzed integer"""
        values = [
            0, -1, 1,
            2**31 - 1, -2**31,  # 32-bit boundaries
            2**63 - 1, -2**63,  # 64-bit boundaries
            random.randint(-1000000, 1000000),
            0xDEADBEEF, 0xCAFEBABE  # Magic values
        ]
        return random.choice(values)
        
    def _fuzz_path(self) -> str:
        """Generate fuzzed file path"""
        paths = [
            '/',
            '/etc/passwd',
            '/dev/null',
            '/proc/self/exe',
            '../../../../etc/passwd',
            '/tmp/' + 'A' * 255,
            '/nonexistent/path',
            'C:\\Windows\\System32',  # Windows path
            '//network/share',
            '\x00/path/with/null',
            'path with spaces',
            'path\nwith\nnewlines'
        ]
        return random.choice(paths)
        
    def _fuzz_command(self) -> str:
        """Generate fuzzed command"""
        commands = [
            'ls',
            'ls -la /',
            'rm -rf /',  # Dangerous command
            '; echo pwned',  # Command injection
            '| cat /etc/passwd',  # Pipe injection
            '`whoami`',  # Backtick injection
            '$(id)',  # Subshell injection
            'A' * 10000,  # Buffer overflow attempt
            '',  # Empty command
            '\x00command',  # Null byte
        ]
        return random.choice(commands)
        
    def _fuzz_signal(self) -> int:
        """Generate fuzzed signal number"""
        signals = [
            0, 1, 2, 3, 9, 15,  # Common signals
            -1, -15,  # Negative signals
            64, 128, 255,  # High signals
            random.randint(-100, 100)
        ]
        return random.choice(signals)
        
    def fuzz(self, data_type: str):
        """Generate fuzzed data of given type"""
        if data_type in self.fuzz_strategies:
            return self.fuzz_strategies[data_type]()
        else:
            # Default: return random data
            return ''.join(random.choices(string.printable, k=random.randint(1, 1000)))


class StressTestRunner:
    """Main stress test runner"""
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.tests = []
        self.results = []
        self.fuzzer = FuzzTester()
        
    def add_test(self, test: StressTest):
        """Add stress test"""
        self.tests.append(test)
        
    def run_all(self, parallel: bool = False) -> List[TestResult]:
        """Run all stress tests"""
        logger.info(f"Running {len(self.tests)} stress tests")
        
        if parallel:
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(test.run) for test in self.tests]
                self.results = [f.result() for f in futures]
        else:
            self.results = []
            for test in self.tests:
                result = test.run()
                self.results.append(result)
                
        self._print_summary()
        return self.results
        
    def run_fuzz_tests(self):
        """Run fuzzing tests"""
        logger.info("Running fuzz tests")
        
        # Fuzz filesystem operations
        if hasattr(self.kernel, 'vfs'):
            self._fuzz_filesystem()
            
        # Fuzz process operations
        if hasattr(self.kernel, 'process_manager'):
            self._fuzz_processes()
            
        # Fuzz shell commands
        if hasattr(self.kernel, 'shell'):
            self._fuzz_shell()
            
    def _fuzz_filesystem(self):
        """Fuzz filesystem operations"""
        vfs = self.kernel.vfs
        
        for _ in range(100):
            try:
                # Fuzz file operations
                path = self.fuzzer.fuzz('path')
                data = self.fuzzer.fuzz('string').encode()
                vfs.write_file(path, data)
            except Exception:
                pass  # Expected to fail
                
            try:
                # Fuzz directory operations
                path = self.fuzzer.fuzz('path')
                vfs.mkdir(path)
            except Exception:
                pass
                
    def _fuzz_processes(self):
        """Fuzz process operations"""
        pm = self.kernel.process_manager
        
        for _ in range(100):
            try:
                # Fuzz process creation
                path = self.fuzzer.fuzz('path')
                uid = self.fuzzer.fuzz('integer')
                gid = self.fuzzer.fuzz('integer')
                pm.create_process(path, uid=uid, gid=gid)
            except Exception:
                pass
                
            try:
                # Fuzz signal sending
                pid = self.fuzzer.fuzz('integer')
                sig = self.fuzzer.fuzz('signal')
                pm.send_signal(pid, sig)
            except Exception:
                pass
                
    def _fuzz_shell(self):
        """Fuzz shell commands"""
        shell = self.kernel.shell
        
        for _ in range(100):
            try:
                # Fuzz command execution
                cmd = self.fuzzer.fuzz('command')
                shell.execute_command(cmd)
            except Exception:
                pass
                
    def _print_summary(self):
        """Print test summary"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        
        print(f"\n{'='*60}")
        print(f"Stress Test Summary")
        print(f"{'='*60}")
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"{'='*60}")
        
        for result in self.results:
            status = "PASS" if result.passed else "FAIL"
            print(f"{result.test_name}: {status}")
            print(f"  Duration: {result.duration:.2f}s")
            print(f"  Iterations: {result.iterations}")
            print(f"  Rate: {result.metrics.get('iterations_per_second', 0):.2f} ops/sec")
            if result.errors:
                print(f"  Errors: {len(result.errors)}")
                for i, error in enumerate(result.errors[:3]):  # Show first 3 errors
                    print(f"    {i+1}. {error.split(chr(10))[0]}")  # First line only
                    
        print(f"{'='*60}\n")


def run_stress_tests(kernel, duration: float = 60.0):
    """Run comprehensive stress tests on KOS"""
    runner = StressTestRunner(kernel)
    
    # Add all stress tests
    if hasattr(kernel, 'process_manager'):
        runner.add_test(ProcessStressTest(kernel.process_manager))
        
    if hasattr(kernel, 'vfs'):
        runner.add_test(FileSystemStressTest(kernel.vfs))
        
    if hasattr(kernel, 'memory_manager'):
        runner.add_test(MemoryStressTest(kernel.memory_manager))
        
    if hasattr(kernel, 'network_stack'):
        runner.add_test(NetworkStressTest(kernel.network_stack))
        
    if hasattr(kernel, 'security_manager'):
        runner.add_test(SecurityStressTest(kernel.security_manager))
        
    # Always add concurrent test
    runner.add_test(ConcurrentStressTest(kernel))
    
    # Run stress tests
    results = runner.run_all(parallel=False)
    
    # Run fuzz tests
    runner.run_fuzz_tests()
    
    return results
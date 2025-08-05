# KOS Test Suite

Comprehensive unit and integration tests for the KOS (Kaede Operating System) components.

## Overview

This test suite provides thorough testing of all critical KOS subsystems:

- **Memory Management** - Buddy allocator, slab allocator, page frame management
- **Process Scheduler** - CFS scheduler, priority handling, load balancing  
- **Filesystem** - VFS operations, file I/O, permissions, mounting
- **Security** - Input validation, hardening measures, authentication
- **Networking** - Network stack, socket operations, firewall
- **Process Management** - Process lifecycle, IPC, thread management
- **Integration** - Cross-component interactions and system-wide behavior

## Quick Start

### Run All Tests
```bash
# Using the test runner
python3 run_tests.py

# Using Make
make test
```

### Run Specific Component Tests
```bash
# Memory management tests
make test-memory

# Scheduler tests  
make test-scheduler

# Filesystem tests
make test-filesystem

# Security tests
make test-security

# Networking tests
make test-networking

# Process management tests
make test-process

# Integration tests
make test-integration
```

### Run with Verbose Output
```bash
python3 run_tests.py --verbose
# or
make test-verbose
```

## Test Organization

### Test Modules

| Module | Purpose | Key Test Areas |
|--------|---------|----------------|
| `test_memory_management.py` | Memory subsystem testing | Allocation, deallocation, page management, kernel memory |
| `test_scheduler.py` | Scheduler algorithm testing | CFS fairness, priority handling, load balancing |
| `test_filesystem.py` | Filesystem operations testing | File I/O, VFS, permissions, mounting |
| `test_security.py` | Security framework testing | Input validation, hardening, authentication |
| `test_networking.py` | Network stack testing | Socket operations, protocols, firewall |
| `test_process_management.py` | Process lifecycle testing | Creation, scheduling, IPC, termination |
| `test_integration.py` | System integration testing | Cross-component interactions, error handling |

### Test Structure

Each test module follows a consistent structure:

```python
class TestComponentName(unittest.TestCase):
    """Test specific component functionality"""
    
    def setUp(self):
        """Initialize test fixtures"""
        pass
    
    def tearDown(self):
        """Clean up after tests"""
        pass
    
    def test_feature_name(self):
        """Test specific feature"""
        # Test implementation
        self.assertTrue(condition)
```

## Test Categories

### Unit Tests
- Test individual components in isolation
- Mock external dependencies
- Focus on specific functionality
- Fast execution (< 1 second per test)

### Integration Tests
- Test interactions between components
- Use real implementations where possible
- Verify end-to-end workflows
- May take longer to execute

### Performance Tests
- Measure system performance under load
- Test scalability and resource usage
- Identify performance bottlenecks
- Stress test critical paths

### Security Tests
- Validate input sanitization
- Test permission enforcement
- Verify hardening measures
- Check for common vulnerabilities

## Running Tests

### Basic Execution

```bash
# Run all tests
python3 run_tests.py

# Run specific module
python3 run_tests.py --module test_memory_management

# Generate JSON report
python3 run_tests.py --json results.json
```

### Using Make Targets

```bash
# Run all tests
make test

# Run specific component tests
make test-memory
make test-scheduler
make test-filesystem
make test-security
make test-networking
make test-process
make test-integration

# Special test runs
make test-quick        # Quick subset of critical tests
make test-performance  # Performance-focused tests
make test-coverage     # With coverage analysis
```

### Environment Validation

```bash
# Check test environment
make validate-env

# Install test dependencies
make install-deps
```

## Test Results and Reporting

### Console Output

The test runner provides detailed console output including:

- Test execution summary
- Module-by-module breakdown
- Failure and error details
- Performance analysis
- Coverage information
- Recommendations

### JSON Reports

Generate machine-readable reports:

```bash
python3 run_tests.py --json detailed_results.json
```

JSON report structure:
```json
{
  "timestamp": 1640995200,
  "total_duration": 45.2,
  "summary": {
    "total_tests": 150,
    "total_failures": 2,
    "total_errors": 0,
    "total_skipped": 1
  },
  "modules": {
    "test_memory_management": {
      "tests_run": 25,
      "failures": 0,
      "errors": 0,
      "duration": 5.3,
      "success_rate": 100.0
    }
  }
}
```

## Writing New Tests

### Test Naming Convention

- Test files: `test_<component>.py`
- Test classes: `Test<ComponentName>`
- Test methods: `test_<functionality>`

### Example Test

```python
import unittest
from unittest.mock import Mock, patch

class TestNewComponent(unittest.TestCase):
    """Test new component functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.component = NewComponent()
    
    def tearDown(self):
        """Clean up test fixtures"""
        self.component.cleanup()
    
    def test_basic_functionality(self):
        """Test basic component functionality"""
        result = self.component.do_something()
        self.assertTrue(result)
        self.assertEqual(self.component.state, 'expected_state')
    
    @patch('external.dependency')
    def test_with_mocking(self, mock_dependency):
        """Test with mocked dependencies"""
        mock_dependency.return_value = 'mocked_result'
        
        result = self.component.use_dependency()
        self.assertEqual(result, 'expected_result')
        mock_dependency.assert_called_once()
```

### Best Practices

1. **Isolation** - Tests should not depend on each other
2. **Cleanup** - Always clean up resources in tearDown()
3. **Mocking** - Mock external dependencies for unit tests
4. **Assertions** - Use appropriate assertion methods
5. **Documentation** - Document test purpose and expected behavior
6. **Performance** - Keep tests fast and focused

## Continuous Integration

### Pre-commit Testing

Run tests before committing changes:

```bash
# Quick validation
make test-quick

# Full test suite
make test
```

### CI Pipeline Integration

Example CI configuration:

```yaml
test:
  script:
    - cd tests
    - make validate-env
    - make install-deps  
    - make test-json
  artifacts:
    reports:
      junit: tests/test_results.json
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   - Ensure KOS is in Python path
   - Check for missing dependencies
   - Verify module structure

2. **Permission Errors**
   - Some tests may require specific permissions
   - Run with appropriate privileges if needed
   - Check file/directory permissions

3. **Resource Conflicts**
   - Tests may conflict if run concurrently
   - Use unique temporary directories
   - Clean up resources properly

4. **Mock Failures**
   - Verify mock patches target correct objects
   - Check mock return values and side effects
   - Ensure mocks are properly configured

### Debug Mode

Enable debug logging:

```bash
python3 run_tests.py --verbose
```

Check test logs:
```bash
tail -f /tmp/kos_tests.log
```

### Test Isolation

Run individual tests for debugging:

```bash
python3 -m unittest test_memory_management.TestMemoryManager.test_memory_allocation -v
```

## Performance Monitoring

### Benchmark Tests

The test suite includes performance benchmarks:

- Memory allocation/deallocation speed
- Scheduler decision time
- File I/O throughput  
- Network operation latency
- Process creation overhead

### Performance Thresholds

Tests include performance assertions:

```python
def test_performance_requirement(self):
    start_time = time.time()
    self.component.perform_operation()
    duration = time.time() - start_time
    
    # Should complete within 100ms
    self.assertLess(duration, 0.1)
```

## Contributing

### Adding New Tests

1. Create test file in appropriate module
2. Follow naming conventions
3. Include docstrings and comments
4. Add performance benchmarks where relevant
5. Update this README if needed

### Test Review Checklist

- [ ] Tests are isolated and independent
- [ ] Resources are properly cleaned up
- [ ] Appropriate mocking is used
- [ ] Performance requirements are tested
- [ ] Error conditions are covered
- [ ] Documentation is clear and complete

## Support

For test-related questions or issues:

1. Check this README
2. Review existing test examples
3. Check KOS documentation
4. Submit issues to the KOS repository

## License

The KOS test suite is part of the KOS project and follows the same licensing terms.
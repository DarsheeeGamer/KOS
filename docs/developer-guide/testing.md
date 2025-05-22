# Testing in KOS

This guide covers testing methodologies, frameworks, and best practices for KOS development.

## Table of Contents
- [Testing Strategy](#testing-strategy)
- [Unit Testing](#unit-testing)
- [Integration Testing](#integration-testing)
- [System Testing](#system-testing)
- [Test Automation](#test-automation)
- [Test Coverage](#test-coverage)
- [Performance Testing](#performance-testing)
- [Security Testing](#security-testing)
- [CI/CD Integration](#cicd-integration)
- [Best Practices](#best-practices)

## Testing Strategy

### Testing Pyramid
```
        /
       / \
      /   \    E2E Tests
     /     \
    /       \
   /         \
  /           \
 /             \
/_______________\ Integration Tests
|               |
|               |
|               |
|               |
| Unit Tests    |
|_______________|
```

### Test Types
1. **Unit Tests**: Test individual components in isolation
2. **Integration Tests**: Test interactions between components
3. **System Tests**: Test the complete system
4. **Performance Tests**: Test system performance
5. **Security Tests**: Test for vulnerabilities
6. **UI Tests**: Test user interface components

## Unit Testing

### Test Framework
```python
# Example unit test using unittest
import unittest
from kos.utils import my_function

class TestMyFunction(unittest.TestCase):
    def test_success(self):
        result = my_function(2, 3)
        self.assertEqual(result, 5)
    
    def test_failure(self):
        with self.assertRaises(ValueError):
            my_function(-1, 3)

if __name__ == '__main__':
    unittest.main()
```

### Running Tests
```bash
# Run all tests
$ python -m unittest discover tests/

# Run specific test
$ python -m unittest tests/test_module.py

# Run with coverage
$ python -m pytest --cov=kos tests/
```

## Integration Testing

### Test Setup
```python
# Example integration test
import unittest
from kos.core import KOS

class TestKOSIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kos = KOS()
        cls.kos.start()
    
    def test_package_installation(self):
        result = self.kos.install_package("example-package")
        self.assertTrue(result.success)
        self.assertIn("example-package", self.kos.list_packages())
    
    @classmethod
    def tearDownClass(cls):
        cls.kos.shutdown()
```

### Mocking Dependencies
```python
from unittest.mock import patch, MagicMock

def test_with_mock():
    with patch('module.function') as mock_func:
        mock_func.return_value = "mocked value"
        result = function_under_test()
        assert result == "expected result"
        mock_func.assert_called_once()
```

## System Testing

### Test Scenarios
```python
def test_system_workflow():
    # 1. Initialize system
    kos = KOS()
    
    # 2. Install package
    kos.install_package("example-package")
    
    # 3. Verify installation
    packages = kos.list_packages()
    assert "example-package" in packages
    
    # 4. Run command
    result = kos.run_command("example-command")
    assert result.exit_code == 0
    
    # 5. Verify output
    assert "expected output" in result.stdout
```

## Test Automation

### Makefile Example
```makefile
.PHONY: test unit integration system

test: unit integration system

unit:
	python -m pytest tests/unit/

integration:
	python -m pytest tests/integration/

system:
	python -m pytest tests/system/

coverage:
	python -m pytest --cov=kos --cov-report=html tests/
```

### GitHub Actions Workflow
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements-dev.txt
    
    - name: Run tests
      run: |
        python -m pytest --cov=kos --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v1
```

## Test Coverage

### Coverage Configuration
```ini
# .coveragerc
[run]
source = kos/
omit = 
    */tests/*
    */__pycache__/*
    */migrations/*

[report]
show_missing = true
skip_covered = true
```

### Coverage Reports
```bash
# Generate HTML report
$ python -m pytest --cov=kos --cov-report=html

# Generate XML report (for CI)
$ python -m pytest --cov=kos --cov-report=xml

# Check coverage from last run
$ python -m coverage report
```

## Performance Testing

### Time Execution
```python
import timeit

def test_performance():
    def function_to_test():
        return sum(range(1000000))
    
    execution_time = timeit.timeit(function_to_test, number=100)
    assert execution_time < 1.0  # seconds
```

### Memory Profiling
```python
import tracemalloc

def test_memory_usage():
    tracemalloc.start()
    
    # Code to test
    result = [i**2 for i in range(100000)]
    
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics('lineno')
    
    for stat in top_stats[:10]:
        print(stat)
    
    assert len(result) == 100000
```

## Security Testing

### Bandit (Security Linter)
```bash
# Install bandit
$ pip install bandit

# Run security scan
$ bandit -r kos/
```

### Dependency Scanning
```bash
# Install safety
$ pip install safety

# Check for vulnerable dependencies
$ safety check
```

## CI/CD Integration

### GitHub Actions
```yaml
name: CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
        ports:
          - 5432:5432
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements-dev.txt
    
    - name: Run tests
      env:
        DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db
      run: |
        python -m pytest
    
    - name: Run security check
      run: |
        pip install safety bandit
        safety check
        bandit -r kos/
```

## Best Practices

### Test Organization
1. Keep tests close to the code they test
2. Use descriptive test names
3. Test one thing per test case
4. Use fixtures for common setup/teardown
5. Keep tests independent and isolated

### Test Data
1. Use factories for test data generation
2. Keep test data minimal and focused
3. Clean up after tests
4. Use test databases for database tests
5. Mock external services

### Test Maintenance
1. Run tests frequently
2. Fix failing tests immediately
3. Review test coverage regularly
4. Refactor tests when code changes
5. Keep tests fast and reliable

## See Also
- [Developer Guide](../developer-guide/README.md)
- [Debugging](./debugging.md)
- [CI/CD Integration](./ci-cd.md)

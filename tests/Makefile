# KOS Test Suite Makefile
# Provides convenient targets for running tests

PYTHON = python3
TEST_DIR = .
KOS_ROOT = ..

.PHONY: all test test-verbose test-memory test-scheduler test-filesystem test-security test-networking test-process test-integration clean help

# Default target
all: test

# Run all tests
test:
	@echo "Running KOS comprehensive test suite..."
	@cd $(TEST_DIR) && $(PYTHON) run_tests.py

# Run tests with verbose output
test-verbose:
	@echo "Running KOS tests with verbose output..."
	@cd $(TEST_DIR) && $(PYTHON) run_tests.py --verbose

# Run specific test modules
test-memory:
	@echo "Running memory management tests..."
	@cd $(TEST_DIR) && $(PYTHON) run_tests.py --module test_memory_management

test-scheduler:
	@echo "Running scheduler tests..."
	@cd $(TEST_DIR) && $(PYTHON) run_tests.py --module test_scheduler

test-filesystem:
	@echo "Running filesystem tests..."
	@cd $(TEST_DIR) && $(PYTHON) run_tests.py --module test_filesystem

test-security:
	@echo "Running security tests..."
	@cd $(TEST_DIR) && $(PYTHON) run_tests.py --module test_security

test-networking:
	@echo "Running networking tests..."
	@cd $(TEST_DIR) && $(PYTHON) run_tests.py --module test_networking

test-process:
	@echo "Running process management tests..."
	@cd $(TEST_DIR) && $(PYTHON) run_tests.py --module test_process_management

test-integration:
	@echo "Running integration tests..."
	@cd $(TEST_DIR) && $(PYTHON) run_tests.py --module test_integration

# Generate JSON report
test-json:
	@echo "Running tests and generating JSON report..."
	@cd $(TEST_DIR) && $(PYTHON) run_tests.py --json test_results.json

# Run tests with coverage (if coverage.py is available)
test-coverage:
	@echo "Running tests with coverage analysis..."
	@cd $(TEST_DIR) && coverage run run_tests.py
	@cd $(TEST_DIR) && coverage report
	@cd $(TEST_DIR) && coverage html

# Quick test (subset of critical tests)
test-quick:
	@echo "Running quick test subset..."
	@cd $(TEST_DIR) && $(PYTHON) -m unittest test_memory_management.TestMemoryManager.test_memory_allocation
	@cd $(TEST_DIR) && $(PYTHON) -m unittest test_scheduler.TestCFSScheduler.test_next_task_selection
	@cd $(TEST_DIR) && $(PYTHON) -m unittest test_filesystem.TestFileSystem.test_file_operations
	@cd $(TEST_DIR) && $(PYTHON) -m unittest test_security.TestInputValidator.test_path_validation

# Performance tests
test-performance:
	@echo "Running performance-focused tests..."
	@cd $(TEST_DIR) && $(PYTHON) -m unittest test_memory_management.TestKernelMemorySubsystem.test_memory_stress
	@cd $(TEST_DIR) && $(PYTHON) -m unittest test_scheduler.TestSchedulerIntegration.test_scheduler_performance
	@cd $(TEST_DIR) && $(PYTHON) -m unittest test_networking.TestKernelNetworkIntegration.test_network_performance
	@cd $(TEST_DIR) && $(PYTHON) -m unittest test_integration.TestPerformanceIntegration.test_concurrent_operations

# Clean up test artifacts
clean:
	@echo "Cleaning up test artifacts..."
	@find . -name "*.pyc" -delete
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@rm -f test_results.json
	@rm -rf htmlcov/
	@rm -f .coverage
	@rm -rf /tmp/kos_test_*
	@rm -rf /tmp/kos_integration_*
	@rm -rf /tmp/kos_proc_fs_*
	@rm -rf /tmp/kos_security_*
	@rm -rf /tmp/kos_vfs_*
	@rm -f /tmp/kos_tests.log

# Install test dependencies
install-deps:
	@echo "Installing test dependencies..."
	@pip install psutil coverage

# Validate test environment
validate-env:
	@echo "Validating test environment..."
	@$(PYTHON) -c "import sys; print(f'Python version: {sys.version}')"
	@$(PYTHON) -c "import unittest; print('unittest available')"
	@$(PYTHON) -c "import threading; print('threading available')"
	@$(PYTHON) -c "import tempfile; print('tempfile available')"
	@$(PYTHON) -c "import socket; print('socket available')"
	@echo "Test environment validation complete"

# Generate test documentation
docs:
	@echo "Generating test documentation..."
	@$(PYTHON) -c "
import sys
sys.path.insert(0, '..')
for module in ['test_memory_management', 'test_scheduler', 'test_filesystem', 'test_security', 'test_networking', 'test_process_management', 'test_integration']:
    try:
        m = __import__(module)
        print(f'=== {module.upper()} ===')
        print(m.__doc__ or 'No documentation available')
        print()
        for name in dir(m):
            if name.startswith('Test'):
                cls = getattr(m, name)
                if hasattr(cls, '__doc__') and cls.__doc__:
                    print(f'{name}: {cls.__doc__.strip()}')
        print()
    except ImportError as e:
        print(f'Could not import {module}: {e}')
"

# Help target
help:
	@echo "KOS Test Suite Makefile"
	@echo "======================="
	@echo ""
	@echo "Available targets:"
	@echo "  test              - Run all tests"
	@echo "  test-verbose      - Run all tests with verbose output"
	@echo "  test-memory       - Run memory management tests"
	@echo "  test-scheduler    - Run scheduler tests"
	@echo "  test-filesystem   - Run filesystem tests"
	@echo "  test-security     - Run security tests"
	@echo "  test-networking   - Run networking tests"
	@echo "  test-process      - Run process management tests"
	@echo "  test-integration  - Run integration tests"
	@echo "  test-json         - Run tests and generate JSON report"
	@echo "  test-coverage     - Run tests with coverage analysis"
	@echo "  test-quick        - Run quick subset of critical tests"
	@echo "  test-performance  - Run performance-focused tests"
	@echo "  clean             - Clean up test artifacts"
	@echo "  install-deps      - Install test dependencies"
	@echo "  validate-env      - Validate test environment"
	@echo "  docs              - Generate test documentation"
	@echo "  help              - Show this help message"
	@echo ""
	@echo "Examples:"
	@echo "  make test                    # Run all tests"
	@echo "  make test-memory             # Run only memory tests"
	@echo "  make test-verbose            # Run with detailed output"
	@echo "  make test-json               # Generate JSON report"
	@echo "  make clean                   # Clean up after tests"
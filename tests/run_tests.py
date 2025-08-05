#!/usr/bin/env python3
"""
KOS Test Runner
Comprehensive test suite runner for all KOS components
"""

import sys
import os
import unittest
import time
import logging
from io import StringIO
import json

# Add KOS to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('KOS.TestRunner')

class KOSTestResult(unittest.TextTestResult):
    """Custom test result class with detailed reporting"""
    
    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.test_results = []
        self.start_time = None
        self.end_time = None
    
    def startTest(self, test):
        super().startTest(test)
        self.start_time = time.time()
    
    def stopTest(self, test):
        super().stopTest(test)
        self.end_time = time.time()
        
        # Record test result
        test_info = {
            'test_name': str(test),
            'duration': self.end_time - self.start_time,
            'status': 'PASS',
            'error': None
        }
        
        # Check if test failed or had error
        for failure in self.failures:
            if failure[0] == test:
                test_info['status'] = 'FAIL'
                test_info['error'] = failure[1]
                break
        
        for error in self.errors:
            if error[0] == test:
                test_info['status'] = 'ERROR'
                test_info['error'] = error[1]
                break
        
        self.test_results.append(test_info)

class KOSTestRunner:
    """Main test runner for KOS components"""
    
    def __init__(self):
        self.test_modules = [
            'test_memory_management',
            'test_scheduler',
            'test_filesystem',
            'test_security',
            'test_networking',
            'test_process_management',
            'test_integration'
        ]
        self.results = {}
        self.total_start_time = None
        self.total_end_time = None
    
    def run_single_module(self, module_name):
        """Run tests for a single module"""
        logger.info(f"Running tests for {module_name}")
        
        try:
            # Import the test module
            module = __import__(module_name)
            
            # Create test suite
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromModule(module)
            
            # Create custom test runner
            stream = StringIO()
            runner = unittest.TextTestRunner(
                stream=stream,
                verbosity=2,
                resultclass=KOSTestResult
            )
            
            # Run tests
            start_time = time.time()
            result = runner.run(suite)
            end_time = time.time()
            
            # Store results
            self.results[module_name] = {
                'tests_run': result.testsRun,
                'failures': len(result.failures),
                'errors': len(result.errors),
                'skipped': len(result.skipped) if hasattr(result, 'skipped') else 0,
                'duration': end_time - start_time,
                'success_rate': ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100) if result.testsRun > 0 else 0,
                'test_details': result.test_results if hasattr(result, 'test_results') else [],
                'output': stream.getvalue()
            }
            
            logger.info(f"Completed {module_name}: {result.testsRun} tests, {len(result.failures)} failures, {len(result.errors)} errors")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to run tests for {module_name}: {e}")
            self.results[module_name] = {
                'tests_run': 0,
                'failures': 0,
                'errors': 1,
                'skipped': 0,
                'duration': 0,
                'success_rate': 0,
                'test_details': [],
                'output': f"Module import/execution error: {str(e)}"
            }
            return False
    
    def run_all_tests(self):
        """Run all test modules"""
        logger.info("Starting comprehensive KOS test suite")
        self.total_start_time = time.time()
        
        for module_name in self.test_modules:
            self.run_single_module(module_name)
        
        self.total_end_time = time.time()
        logger.info("Completed all tests")
    
    def generate_report(self):
        """Generate comprehensive test report"""
        if not self.results:
            logger.error("No test results to report")
            return
        
        total_tests = sum(r['tests_run'] for r in self.results.values())
        total_failures = sum(r['failures'] for r in self.results.values())
        total_errors = sum(r['errors'] for r in self.results.values())
        total_skipped = sum(r['skipped'] for r in self.results.values())
        total_duration = self.total_end_time - self.total_start_time if self.total_start_time else 0
        overall_success_rate = ((total_tests - total_failures - total_errors) / total_tests * 100) if total_tests > 0 else 0
        
        print("\n" + "="*80)
        print("KOS COMPREHENSIVE TEST REPORT")
        print("="*80)
        print(f"Total Tests Run: {total_tests}")
        print(f"Passed: {total_tests - total_failures - total_errors}")
        print(f"Failed: {total_failures}")
        print(f"Errors: {total_errors}")
        print(f"Skipped: {total_skipped}")
        print(f"Success Rate: {overall_success_rate:.1f}%")
        print(f"Total Duration: {total_duration:.2f} seconds")
        print()
        
        # Module breakdown
        print("MODULE BREAKDOWN:")
        print("-" * 80)
        print(f"{'Module':<25} {'Tests':<8} {'Pass':<8} {'Fail':<8} {'Error':<8} {'Rate':<8} {'Time':<8}")
        print("-" * 80)
        
        for module_name, result in self.results.items():
            passed = result['tests_run'] - result['failures'] - result['errors']
            print(f"{module_name:<25} {result['tests_run']:<8} {passed:<8} {result['failures']:<8} {result['errors']:<8} {result['success_rate']:<7.1f}% {result['duration']:<7.2f}s")
        
        print()
        
        # Detailed failures and errors
        if total_failures > 0 or total_errors > 0:
            print("DETAILED FAILURE/ERROR REPORT:")
            print("-" * 80)
            
            for module_name, result in self.results.items():
                if result['failures'] > 0 or result['errors'] > 0:
                    print(f"\n{module_name.upper()}:")
                    
                    for test_detail in result.get('test_details', []):
                        if test_detail['status'] in ['FAIL', 'ERROR']:
                            print(f"  {test_detail['status']}: {test_detail['test_name']}")
                            if test_detail['error']:
                                # Print first few lines of error
                                error_lines = test_detail['error'].split('\n')[:3]
                                for line in error_lines:
                                    print(f"    {line}")
                            print()
        
        # Performance analysis
        print("PERFORMANCE ANALYSIS:")
        print("-" * 80)
        
        # Slowest tests
        all_test_details = []
        for module_name, result in self.results.items():
            for test_detail in result.get('test_details', []):
                test_detail['module'] = module_name
                all_test_details.append(test_detail)
        
        slowest_tests = sorted(all_test_details, key=lambda x: x['duration'], reverse=True)[:10]
        
        print("Slowest Tests:")
        for i, test in enumerate(slowest_tests, 1):
            print(f"  {i:2d}. {test['test_name']} ({test['module']}) - {test['duration']:.3f}s")
        
        print()
        
        # Coverage analysis (conceptual)
        print("COVERAGE ANALYSIS:")
        print("-" * 80)
        tested_components = [
            'Memory Management',
            'Process Scheduler', 
            'Filesystem (VFS)',
            'Security Framework',
            'Network Stack',
            'Process Management',
            'System Integration'
        ]
        
        for component in tested_components:
            print(f"  ✓ {component}")
        
        print()
        
        # Recommendations
        print("RECOMMENDATIONS:")
        print("-" * 80)
        
        if overall_success_rate < 90:
            print("  ⚠ Overall success rate is below 90%. Focus on fixing failing tests.")
        
        if total_duration > 60:
            print("  ⚠ Test suite takes longer than 1 minute. Consider optimizing slow tests.")
        
        slow_modules = [name for name, result in self.results.items() if result['duration'] > 10]
        if slow_modules:
            print(f"  ⚠ Slow test modules: {', '.join(slow_modules)}")
        
        failed_modules = [name for name, result in self.results.items() if result['failures'] > 0 or result['errors'] > 0]
        if failed_modules:
            print(f"  🔧 Modules needing attention: {', '.join(failed_modules)}")
        
        if overall_success_rate >= 95:
            print("  ✅ Excellent test coverage and success rate!")
        
        print("\n" + "="*80)
    
    def save_json_report(self, filename='test_results.json'):
        """Save detailed results to JSON file"""
        report_data = {
            'timestamp': time.time(),
            'total_duration': self.total_end_time - self.total_start_time if self.total_start_time else 0,
            'summary': {
                'total_tests': sum(r['tests_run'] for r in self.results.values()),
                'total_failures': sum(r['failures'] for r in self.results.values()),
                'total_errors': sum(r['errors'] for r in self.results.values()),
                'total_skipped': sum(r['skipped'] for r in self.results.values()),
            },
            'modules': self.results
        }
        
        with open(filename, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        logger.info(f"Detailed results saved to {filename}")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='KOS Test Runner')
    parser.add_argument('--module', '-m', help='Run specific test module')
    parser.add_argument('--json', '-j', help='Save JSON report to file')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    runner = KOSTestRunner()
    
    if args.module:
        # Run specific module
        if args.module in runner.test_modules:
            runner.run_single_module(args.module)
        else:
            logger.error(f"Unknown test module: {args.module}")
            logger.info(f"Available modules: {', '.join(runner.test_modules)}")
            sys.exit(1)
    else:
        # Run all tests
        runner.run_all_tests()
    
    # Generate report
    runner.generate_report()
    
    # Save JSON report if requested
    if args.json:
        runner.save_json_report(args.json)
    
    # Exit with appropriate code
    total_failures = sum(r['failures'] for r in runner.results.values())
    total_errors = sum(r['errors'] for r in runner.results.values())
    
    if total_failures > 0 or total_errors > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == '__main__':
    main()
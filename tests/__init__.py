"""
KOS Test Suite
Unit tests for critical KOS components
"""

import sys
import os
import unittest
import logging

# Add KOS to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Configure logging for tests
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/kos_tests.log')
    ]
)

def run_all_tests():
    """Run all KOS tests"""
    loader = unittest.TestLoader()
    suite = loader.discover('tests', pattern='test_*.py')
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)

if __name__ == '__main__':
    run_all_tests()
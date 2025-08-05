"""
Unit tests for KOS security components
"""

import unittest
import tempfile
import os
import sys
import time
from unittest.mock import Mock, patch, MagicMock

# Add KOS to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from kos.security.hardening import (
    SecurityManager, InputValidator, MemoryProtection, 
    CryptoHardening, ProcessHardening, SecurityLevel,
    ThreatType, SecurityViolation
)
from kos.security.auth import AuthenticationManager
from kos.security.manager import SecurityManager as CoreSecurityManager

class TestInputValidator(unittest.TestCase):
    """Test input validation security measures"""
    
    def test_path_validation(self):
        """Test path validation"""
        # Valid paths
        valid_paths = [
            '/home/user/file.txt',
            'relative/path/file.txt',
            '/tmp/tempfile',
        ]
        
        for path in valid_paths:
            valid, msg = InputValidator.validate_path(path, allow_absolute=True)
            self.assertTrue(valid, f"Path {path} should be valid: {msg}")
        
        # Invalid paths
        invalid_paths = [
            '../../../etc/passwd',  # Path traversal
            '/proc/self/mem',       # Dangerous system path
            'file\x00name',         # Null byte
            'file\x01name',         # Control character
            'a' * 5000,             # Too long
        ]
        
        for path in invalid_paths:
            valid, msg = InputValidator.validate_path(path)
            self.assertFalse(valid, f"Path {path} should be invalid")
    
    def test_username_validation(self):
        """Test username validation"""
        # Valid usernames
        valid_usernames = [
            'user123',
            'alice',
            'user_name',
            'user-name',
        ]
        
        for username in valid_usernames:
            valid, msg = InputValidator.validate_username(username)
            self.assertTrue(valid, f"Username {username} should be valid: {msg}")
        
        # Invalid usernames
        invalid_usernames = [
            '123user',      # Starts with number
            'user@host',    # Invalid character
            '',             # Empty
            'a' * 50,       # Too long
            'user name',    # Space
        ]
        
        for username in invalid_usernames:
            valid, msg = InputValidator.validate_username(username)
            self.assertFalse(valid, f"Username {username} should be invalid")
    
    def test_command_validation(self):
        """Test command validation"""
        # Valid commands
        valid_commands = [
            'ls -la',
            'cat file.txt',
            'grep pattern file',
        ]
        
        for command in valid_commands:
            valid, msg = InputValidator.validate_command(command)
            self.assertTrue(valid, f"Command {command} should be valid: {msg}")
        
        # Dangerous commands
        dangerous_commands = [
            'rm -rf /',
            'dd if=/dev/zero of=/dev/sda',
            'mkfs.ext4 /dev/sda1',
            'format c:',
        ]
        
        for command in dangerous_commands:
            valid, msg = InputValidator.validate_command(command)
            self.assertFalse(valid, f"Command {command} should be invalid")
    
    def test_string_sanitization(self):
        """Test string sanitization"""
        # Test with control characters
        dirty_string = "Hello\x00World\x01Test\x02"
        clean_string = InputValidator.sanitize_string(dirty_string)
        
        # Should remove control characters except allowed ones
        self.assertNotIn('\x00', clean_string)
        self.assertNotIn('\x01', clean_string)
        self.assertNotIn('\x02', clean_string)
        
        # Test length truncation
        long_string = 'a' * 2000
        truncated = InputValidator.sanitize_string(long_string, max_length=100)
        self.assertEqual(len(truncated), 100)

class TestMemoryProtection(unittest.TestCase):
    """Test memory protection mechanisms"""
    
    def test_secure_zero(self):
        """Test secure memory zeroing"""
        # Create test data
        test_data = bytearray(b'sensitive_password_123')
        original_len = len(test_data)
        
        # Zero memory securely
        MemoryProtection.secure_zero(test_data)
        
        # Memory should be zeroed and overwritten
        self.assertEqual(len(test_data), original_len)
        # Content should be changed (not necessarily all zeros due to overwrite passes)
        self.assertNotEqual(test_data, bytearray(b'sensitive_password_123'))
    
    def test_buffer_bounds_validation(self):
        """Test buffer bounds checking"""
        buffer = b'Hello World'
        
        # Valid access
        self.assertTrue(MemoryProtection.validate_buffer_bounds(buffer, 0, 5))
        self.assertTrue(MemoryProtection.validate_buffer_bounds(buffer, 6, 5))
        
        # Invalid access
        self.assertFalse(MemoryProtection.validate_buffer_bounds(buffer, -1, 5))
        self.assertFalse(MemoryProtection.validate_buffer_bounds(buffer, 0, -1))
        self.assertFalse(MemoryProtection.validate_buffer_bounds(buffer, 0, 20))  # Exceeds buffer
        self.assertFalse(MemoryProtection.validate_buffer_bounds(buffer, 10, 5))  # Offset + length > buffer
    
    def test_safe_copy(self):
        """Test safe memory copy operations"""
        src = b'Source data'
        dest = bytearray(20)  # Larger destination
        
        # Valid copy
        result = MemoryProtection.safe_copy(dest, src, 20)
        self.assertTrue(result)
        self.assertEqual(dest[:len(src)], src)
        
        # Copy too large for destination
        small_dest = bytearray(5)
        result = MemoryProtection.safe_copy(small_dest, src, 20)
        self.assertFalse(result)
        
        # Source too large for max_size
        result = MemoryProtection.safe_copy(dest, src, 5)
        self.assertFalse(result)

class TestCryptoHardening(unittest.TestCase):
    """Test cryptographic security measures"""
    
    def test_secure_random_generation(self):
        """Test cryptographically secure random generation"""
        # Generate random bytes
        random_data1 = CryptoHardening.secure_random_bytes(32)
        random_data2 = CryptoHardening.secure_random_bytes(32)
        
        self.assertEqual(len(random_data1), 32)
        self.assertEqual(len(random_data2), 32)
        self.assertNotEqual(random_data1, random_data2)  # Should be different
    
    def test_secure_hashing(self):
        """Test secure hashing functions"""
        data = b'test_password'
        salt = b'random_salt_123'
        
        # Hash with salt
        hash1 = CryptoHardening.secure_hash(data, salt)
        hash2 = CryptoHardening.secure_hash(data, salt)
        
        # Same input should produce same hash
        self.assertEqual(hash1, hash2)
        
        # Different salt should produce different hash
        different_salt = b'different_salt'
        hash3 = CryptoHardening.secure_hash(data, different_salt)
        self.assertNotEqual(hash1, hash3)
    
    def test_constant_time_compare(self):
        """Test constant-time comparison"""
        data1 = b'secret_token'
        data2 = b'secret_token'
        data3 = b'different_token'
        
        # Same data should match
        self.assertTrue(CryptoHardening.constant_time_compare(data1, data2))
        
        # Different data should not match
        self.assertFalse(CryptoHardening.constant_time_compare(data1, data3))
    
    def test_token_generation(self):
        """Test secure token generation"""
        token1 = CryptoHardening.generate_token(32)
        token2 = CryptoHardening.generate_token(32)
        
        self.assertIsInstance(token1, str)
        self.assertIsInstance(token2, str)
        self.assertNotEqual(token1, token2)
        
        # Test different lengths
        short_token = CryptoHardening.generate_token(16)
        long_token = CryptoHardening.generate_token(64)
        
        self.assertNotEqual(len(short_token), len(long_token))

class TestProcessHardening(unittest.TestCase):
    """Test process hardening measures"""
    
    @patch('os.getuid')
    @patch('os.setuid')
    @patch('os.setgid')
    def test_privilege_dropping(self, mock_setgid, mock_setuid, mock_getuid):
        """Test privilege dropping"""
        # Mock running as root
        mock_getuid.return_value = 0
        
        # Mock successful privilege drop
        mock_setgid.return_value = None
        mock_setuid.side_effect = [None, PermissionError()]  # First call succeeds, second fails (good)
        
        result = ProcessHardening.drop_privileges()
        self.assertTrue(result)
    
    @patch('resource.setrlimit')
    def test_process_limits(self, mock_setrlimit):
        """Test process resource limits"""
        mock_setrlimit.return_value = None
        
        # Should not raise exception
        ProcessHardening.set_process_limits()
        
        # Verify that limits were set
        self.assertTrue(mock_setrlimit.called)
    
    @patch('builtins.open', create=True)
    def test_aslr_check(self, mock_open):
        """Test ASLR enablement check"""
        # Mock ASLR enabled
        mock_file = MagicMock()
        mock_file.read.return_value = '2\n'
        mock_open.return_value.__enter__.return_value = mock_file
        
        result = ProcessHardening.enable_aslr()
        self.assertTrue(result)
        
        # Mock ASLR disabled
        mock_file.read.return_value = '0\n'
        result = ProcessHardening.enable_aslr()
        self.assertFalse(result)

class TestSecurityManager(unittest.TestCase):
    """Test main security manager"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.security_manager = SecurityManager(SecurityLevel.STANDARD)
    
    def test_security_manager_initialization(self):
        """Test security manager initialization"""
        self.assertEqual(self.security_manager.security_level, SecurityLevel.STANDARD)
        self.assertIsNotNone(self.security_manager.auditor)
        self.assertFalse(self.security_manager.hardening_enabled)
    
    @patch('kos.security.hardening.ProcessHardening.set_process_limits')
    @patch('kos.security.hardening.ProcessHardening.enable_aslr')
    @patch('kos.security.hardening.NetworkHardening.setup_firewall_rules')
    def test_hardening_initialization(self, mock_firewall, mock_aslr, mock_limits):
        """Test security hardening initialization"""
        mock_aslr.return_value = True
        mock_firewall.return_value = True
        
        result = self.security_manager.initialize_hardening()
        self.assertTrue(result)
        self.assertTrue(self.security_manager.hardening_enabled)
    
    def test_input_validation_integration(self):
        """Test input validation through security manager"""
        # Test path validation
        valid, msg = self.security_manager.validate_input('/home/user/file.txt', 'path')
        self.assertTrue(valid)
        
        # Test username validation
        valid, msg = self.security_manager.validate_input('testuser', 'username')
        self.assertTrue(valid)
        
        # Test command validation
        valid, msg = self.security_manager.validate_input('ls -la', 'command')
        self.assertTrue(valid)
    
    def test_security_metrics(self):
        """Test security metrics collection"""
        metrics = self.security_manager.get_security_metrics()
        
        self.assertIsInstance(metrics, dict)
        self.assertIn('hardening_enabled', metrics)
        self.assertIn('security_level', metrics)
        self.assertIn('audit_report', metrics)

class TestSecurityAuditor(unittest.TestCase):
    """Test security auditing functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.security_manager = SecurityManager()
        self.auditor = self.security_manager.auditor
    
    def test_violation_recording(self):
        """Test security violation recording"""
        violation = SecurityViolation(
            threat_type=ThreatType.BUFFER_OVERFLOW,
            severity="HIGH",
            description="Test violation",
            location="test_function",
            timestamp=time.time(),
            remediation="Fix the buffer overflow"
        )
        
        initial_count = len(self.auditor.violations)
        self.auditor.record_violation(violation)
        
        self.assertEqual(len(self.auditor.violations), initial_count + 1)
        self.assertIn(violation, self.auditor.violations)
    
    def test_security_report_generation(self):
        """Test security report generation"""
        # Add some test violations
        for i in range(5):
            violation = SecurityViolation(
                threat_type=ThreatType.PRIVILEGE_ESCALATION,
                severity="MEDIUM",
                description=f"Test violation {i}",
                location=f"function_{i}",
                timestamp=time.time(),
                remediation="Test remediation"
            )
            self.auditor.record_violation(violation)
        
        report = self.auditor.get_security_report()
        
        self.assertIsInstance(report, dict)
        self.assertIn('total_violations', report)
        self.assertIn('threat_counts', report)
        self.assertIn('severity_counts', report)
        self.assertEqual(report['total_violations'], 5)
    
    @patch('os.walk')
    @patch('os.stat')
    def test_file_permission_audit(self, mock_stat, mock_walk):
        """Test file permissions auditing"""
        # Mock file system walk
        mock_walk.return_value = [
            ('/test', [], ['file1.txt', 'file2.txt'])
        ]
        
        # Mock stat for world-writable file
        mock_stat_result = MagicMock()
        mock_stat_result.st_mode = 0o100666  # World-writable file
        mock_stat.return_value = mock_stat_result
        
        violations = self.auditor.audit_file_permissions('/test')
        
        # Should detect world-writable files as violations
        self.assertGreater(len(violations), 0)
        self.assertEqual(violations[0].threat_type, ThreatType.PRIVILEGE_ESCALATION)
    
    @patch('os.getuid')
    def test_privilege_audit(self, mock_getuid):
        """Test privilege auditing"""
        # Mock running as root
        mock_getuid.return_value = 0
        
        violations = self.auditor.audit_process_privileges()
        
        # Should detect running as root as a violation
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].threat_type, ThreatType.PRIVILEGE_ESCALATION)

class TestAuthenticationManager(unittest.TestCase):
    """Test authentication system"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.auth_manager = AuthenticationManager()
    
    def test_user_creation(self):
        """Test user creation"""
        username = 'testuser'
        password = 'secure_password_123'
        
        result = self.auth_manager.create_user(username, password)
        self.assertTrue(result)
        
        # User should exist
        self.assertTrue(self.auth_manager.user_exists(username))
    
    def test_authentication(self):
        """Test user authentication"""
        username = 'authtest'
        password = 'test_password'
        
        # Create user
        self.auth_manager.create_user(username, password)
        
        # Test correct authentication
        result = self.auth_manager.authenticate(username, password)
        self.assertTrue(result)
        
        # Test incorrect password
        result = self.auth_manager.authenticate(username, 'wrong_password')
        self.assertFalse(result)
        
        # Test non-existent user
        result = self.auth_manager.authenticate('nonexistent', password)
        self.assertFalse(result)
    
    def test_password_policy(self):
        """Test password policy enforcement"""
        username = 'policytest'
        
        # Test weak passwords
        weak_passwords = [
            '123',          # Too short
            'password',     # Common password
            'abc',          # Too simple
        ]
        
        for password in weak_passwords:
            result = self.auth_manager.create_user(username + password, password)
            # Should fail with weak password
            self.assertFalse(result)
        
        # Test strong password
        strong_password = 'Str0ng_P@ssw0rd_123!'
        result = self.auth_manager.create_user(username, strong_password)
        self.assertTrue(result)
    
    def test_session_management(self):
        """Test session management"""
        username = 'sessiontest'
        password = 'session_password'
        
        # Create user
        self.auth_manager.create_user(username, password)
        
        # Create session
        session_id = self.auth_manager.create_session(username)
        self.assertIsNotNone(session_id)
        
        # Validate session
        self.assertTrue(self.auth_manager.validate_session(session_id))
        
        # Destroy session
        self.auth_manager.destroy_session(session_id)
        self.assertFalse(self.auth_manager.validate_session(session_id))

class TestKernelSecurityIntegration(unittest.TestCase):
    """Test kernel security integration"""
    
    @patch('kos.kernel.security.security_wrapper')
    def test_kernel_security_functions(self, mock_security):
        """Test kernel security function integration"""
        # Mock security functions
        mock_security.security_init.return_value = 0
        mock_security.check_permission.return_value = 1  # Permission granted
        mock_security.audit_log.return_value = 0
        
        from kos.kernel.security.security_wrapper import security_init, check_permission, audit_log
        
        # Test initialization
        result = security_init()
        self.assertEqual(result, 0)
        
        # Test permission checking
        has_permission = check_permission(1000, "read", "/etc/passwd")
        self.assertEqual(has_permission, 1)
        
        # Test audit logging
        result = audit_log("user_login", "testuser", "192.168.1.100")
        self.assertEqual(result, 0)
    
    def test_security_performance(self):
        """Test security system performance"""
        security_manager = SecurityManager()
        
        # Time multiple validations
        start_time = time.time()
        
        for i in range(1000):
            InputValidator.validate_path(f'/test/path_{i}.txt')
            InputValidator.validate_username(f'user_{i}')
        
        elapsed_time = time.time() - start_time
        
        # Should complete validations quickly
        self.assertLess(elapsed_time, 1.0)  # Less than 1 second for 2000 validations

if __name__ == '__main__':
    unittest.main()
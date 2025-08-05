"""
Unit tests for KOS filesystem components
"""

import unittest
import tempfile
import os
import sys
import shutil
from unittest.mock import Mock, patch, MagicMock

# Add KOS to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from kos.filesystem.base import FileSystem
from kos.filesystem.vfs import VirtualFileSystem
from kos.filesystem.ramfs import RAMFileSystem
from kos.core.filesystem.fs_manager import FileSystemManager

class TestFileSystem(unittest.TestCase):
    """Test base filesystem functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.fs = FileSystem()
        self.test_dir = tempfile.mkdtemp(prefix='kos_test_')
    
    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_filesystem_initialization(self):
        """Test filesystem initialization"""
        self.assertIsNotNone(self.fs)
        self.assertTrue(hasattr(self.fs, 'mount_point'))
        self.assertTrue(hasattr(self.fs, 'fs_type'))
    
    def test_file_operations(self):
        """Test basic file operations"""
        test_file = os.path.join(self.test_dir, 'test.txt')
        test_content = b'Hello, KOS!'
        
        # Test file creation and writing
        result = self.fs.create_file(test_file, test_content)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(test_file))
        
        # Test file reading
        content = self.fs.read_file(test_file)
        self.assertEqual(content, test_content)
        
        # Test file deletion
        result = self.fs.delete_file(test_file)
        self.assertTrue(result)
        self.assertFalse(os.path.exists(test_file))
    
    def test_directory_operations(self):
        """Test directory operations"""
        test_subdir = os.path.join(self.test_dir, 'subdir')
        
        # Test directory creation
        result = self.fs.create_directory(test_subdir)
        self.assertTrue(result)
        self.assertTrue(os.path.isdir(test_subdir))
        
        # Test directory listing
        files = self.fs.list_directory(self.test_dir)
        self.assertIsInstance(files, list)
        self.assertIn('subdir', files)
        
        # Test directory removal
        result = self.fs.remove_directory(test_subdir)
        self.assertTrue(result)
        self.assertFalse(os.path.exists(test_subdir))
    
    def test_file_permissions(self):
        """Test file permission handling"""
        test_file = os.path.join(self.test_dir, 'perm_test.txt')
        
        # Create file
        self.fs.create_file(test_file, b'test content')
        
        # Test permission setting
        result = self.fs.set_permissions(test_file, 0o644)
        self.assertTrue(result)
        
        # Test permission getting
        perms = self.fs.get_permissions(test_file)
        self.assertEqual(perms & 0o777, 0o644)
    
    def test_file_metadata(self):
        """Test file metadata operations"""
        test_file = os.path.join(self.test_dir, 'meta_test.txt')
        content = b'metadata test'
        
        self.fs.create_file(test_file, content)
        
        # Get file metadata
        metadata = self.fs.get_metadata(test_file)
        self.assertIsInstance(metadata, dict)
        self.assertIn('size', metadata)
        self.assertIn('mtime', metadata)
        self.assertIn('ctime', metadata)
        self.assertEqual(metadata['size'], len(content))

class TestVirtualFileSystem(unittest.TestCase):
    """Test Virtual File System"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.vfs = VirtualFileSystem()
        self.test_mount = tempfile.mkdtemp(prefix='kos_vfs_')
    
    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.test_mount):
            shutil.rmtree(self.test_mount)
    
    def test_vfs_initialization(self):
        """Test VFS initialization"""
        self.assertIsNotNone(self.vfs)
        self.assertIsInstance(self.vfs.mounts, dict)
        self.assertIsInstance(self.vfs.inodes, dict)
    
    def test_filesystem_mounting(self):
        """Test filesystem mounting"""
        fs = FileSystem()
        
        # Mount filesystem
        result = self.vfs.mount(fs, '/test')
        self.assertTrue(result)
        self.assertIn('/test', self.vfs.mounts)
        
        # Unmount filesystem
        result = self.vfs.unmount('/test')
        self.assertTrue(result)
        self.assertNotIn('/test', self.vfs.mounts)
    
    def test_path_resolution(self):
        """Test path resolution"""
        # Test absolute path
        resolved = self.vfs.resolve_path('/usr/bin/test')
        self.assertEqual(resolved, '/usr/bin/test')
        
        # Test relative path resolution
        self.vfs.current_dir = '/home/user'
        resolved = self.vfs.resolve_path('documents/file.txt')
        self.assertEqual(resolved, '/home/user/documents/file.txt')
    
    def test_path_traversal_protection(self):
        """Test path traversal attack protection"""
        # Test dangerous paths
        dangerous_paths = [
            '../../../etc/passwd',
            '/etc/../../../etc/passwd',
            '..\\..\\..\\windows\\system32',
        ]
        
        for path in dangerous_paths:
            with self.assertRaises(ValueError):
                self.vfs.resolve_path(path, safe=True)
    
    def test_inode_operations(self):
        """Test inode operations"""
        # Create inode
        inode_num = self.vfs.create_inode('/test/file', 'file')
        self.assertGreater(inode_num, 0)
        self.assertIn(inode_num, self.vfs.inodes)
        
        # Get inode
        inode = self.vfs.get_inode(inode_num)
        self.assertIsNotNone(inode)
        self.assertEqual(inode['path'], '/test/file')
        self.assertEqual(inode['type'], 'file')
        
        # Delete inode
        result = self.vfs.delete_inode(inode_num)
        self.assertTrue(result)
        self.assertNotIn(inode_num, self.vfs.inodes)
    
    def test_file_descriptors(self):
        """Test file descriptor management"""
        # Open file
        fd = self.vfs.open('/test/file', 'w')
        self.assertGreater(fd, 0)
        
        # Check file descriptor
        fd_info = self.vfs.get_fd_info(fd)
        self.assertIsNotNone(fd_info)
        self.assertEqual(fd_info['path'], '/test/file')
        self.assertEqual(fd_info['mode'], 'w')
        
        # Close file
        result = self.vfs.close(fd)
        self.assertTrue(result)

class TestRAMFileSystem(unittest.TestCase):
    """Test RAM-based filesystem"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.ramfs = RAMFileSystem()
    
    def test_ramfs_initialization(self):
        """Test RAMFS initialization"""
        self.assertIsNotNone(self.ramfs)
        self.assertIsInstance(self.ramfs.files, dict)
        self.assertIsInstance(self.ramfs.directories, dict)
    
    def test_in_memory_file_operations(self):
        """Test in-memory file operations"""
        filename = '/test/memory_file.txt'
        content = b'This is stored in RAM'
        
        # Create file in memory
        result = self.ramfs.create_file(filename, content)
        self.assertTrue(result)
        self.assertIn(filename, self.ramfs.files)
        
        # Read file from memory
        read_content = self.ramfs.read_file(filename)
        self.assertEqual(read_content, content)
        
        # Modify file in memory
        new_content = b'Modified content'
        result = self.ramfs.write_file(filename, new_content)
        self.assertTrue(result)
        
        modified_content = self.ramfs.read_file(filename)
        self.assertEqual(modified_content, new_content)
        
        # Delete file from memory
        result = self.ramfs.delete_file(filename)
        self.assertTrue(result)
        self.assertNotIn(filename, self.ramfs.files)
    
    def test_ramfs_performance(self):
        """Test RAMFS performance characteristics"""
        import time
        
        filename = '/perf/test.bin'
        large_content = b'x' * (1024 * 1024)  # 1MB
        
        # Test write performance
        start_time = time.time()
        self.ramfs.create_file(filename, large_content)
        write_time = time.time() - start_time
        
        # Test read performance
        start_time = time.time()
        read_content = self.ramfs.read_file(filename)
        read_time = time.time() - start_time
        
        # RAM operations should be fast
        self.assertLess(write_time, 0.1)  # < 100ms for 1MB write
        self.assertLess(read_time, 0.1)   # < 100ms for 1MB read
        self.assertEqual(len(read_content), len(large_content))
    
    def test_memory_usage(self):
        """Test memory usage tracking"""
        # Get initial memory usage
        initial_usage = self.ramfs.get_memory_usage()
        
        # Create several files
        for i in range(10):
            filename = f'/mem_test/file_{i}.txt'
            content = b'x' * 1024  # 1KB each
            self.ramfs.create_file(filename, content)
        
        # Check memory usage increased
        final_usage = self.ramfs.get_memory_usage()
        self.assertGreater(final_usage, initial_usage)
        
        # Should be approximately 10KB increase
        usage_diff = final_usage - initial_usage
        self.assertGreaterEqual(usage_diff, 10240)  # At least 10KB

class TestFileSystemManager(unittest.TestCase):
    """Test filesystem manager"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.fs_manager = FileSystemManager()
    
    def test_manager_initialization(self):
        """Test filesystem manager initialization"""
        self.assertIsNotNone(self.fs_manager)
        self.assertIsInstance(self.fs_manager.filesystems, dict)
    
    def test_filesystem_registration(self):
        """Test filesystem type registration"""
        fs = FileSystem()
        
        # Register filesystem type
        result = self.fs_manager.register_filesystem('test_fs', fs)
        self.assertTrue(result)
        self.assertIn('test_fs', self.fs_manager.filesystems)
        
        # Unregister filesystem type
        result = self.fs_manager.unregister_filesystem('test_fs')
        self.assertTrue(result)
        self.assertNotIn('test_fs', self.fs_manager.filesystems)
    
    def test_filesystem_creation(self):
        """Test filesystem creation"""
        # Register a filesystem type first
        ramfs = RAMFileSystem()
        self.fs_manager.register_filesystem('ramfs', ramfs)
        
        # Create filesystem instance
        fs_instance = self.fs_manager.create_filesystem('ramfs')
        self.assertIsNotNone(fs_instance)
        self.assertIsInstance(fs_instance, RAMFileSystem)
    
    def test_mount_management(self):
        """Test mount point management"""
        fs = FileSystem()
        mount_point = '/test_mount'
        
        # Mount filesystem
        result = self.fs_manager.mount(fs, mount_point)
        self.assertTrue(result)
        
        # Check mount exists
        self.assertTrue(self.fs_manager.is_mounted(mount_point))
        
        # Get mounted filesystem
        mounted_fs = self.fs_manager.get_mounted_fs(mount_point)
        self.assertEqual(mounted_fs, fs)
        
        # Unmount filesystem
        result = self.fs_manager.unmount(mount_point)
        self.assertTrue(result)
        self.assertFalse(self.fs_manager.is_mounted(mount_point))

class TestKernelVFSIntegration(unittest.TestCase):
    """Test VFS integration with kernel"""
    
    @patch('kos.vfs.vfs_wrapper')
    def test_kernel_vfs_operations(self, mock_vfs):
        """Test kernel VFS integration"""
        # Mock VFS functions
        mock_vfs.vfs_open.return_value = 5  # File descriptor
        mock_vfs.vfs_read.return_value = 10  # Bytes read
        mock_vfs.vfs_write.return_value = 10  # Bytes written
        mock_vfs.vfs_close.return_value = 0  # Success
        
        from kos.vfs.vfs_wrapper import vfs_open, vfs_read, vfs_write, vfs_close
        
        # Test file operations
        fd = vfs_open("/test/file", "O_RDWR")
        self.assertEqual(fd, 5)
        
        buffer = b"test data"
        bytes_written = vfs_write(fd, buffer, len(buffer))
        self.assertEqual(bytes_written, 10)
        
        bytes_read = vfs_read(fd, len(buffer))
        self.assertEqual(bytes_read, 10)
        
        result = vfs_close(fd)
        self.assertEqual(result, 0)
    
    def test_filesystem_stress(self):
        """Stress test filesystem operations"""
        vfs = VirtualFileSystem()
        
        # Create many files
        num_files = 1000
        for i in range(num_files):
            filename = f'/stress/file_{i}.txt'
            content = f'File {i} content'.encode()
            
            # This tests the filesystem's ability to handle many files
            fd = vfs.open(filename, 'w')
            self.assertGreater(fd, 0)
            vfs.close(fd)
        
        # Test should complete without errors
        self.assertTrue(True)
    
    def test_concurrent_access(self):
        """Test concurrent filesystem access"""
        import threading
        
        vfs = VirtualFileSystem()
        results = []
        
        def worker(worker_id):
            try:
                filename = f'/concurrent/worker_{worker_id}.txt'
                content = f'Worker {worker_id} data'.encode()
                
                # Each worker creates and manipulates its own file
                fd = vfs.open(filename, 'w')
                if fd > 0:
                    vfs.close(fd)
                    results.append(True)
                else:
                    results.append(False)
            except Exception:
                results.append(False)
        
        # Start multiple worker threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All workers should succeed
        self.assertEqual(len(results), 10)
        self.assertTrue(all(results))

if __name__ == '__main__':
    unittest.main()
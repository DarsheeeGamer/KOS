#!/usr/bin/env python3
"""
Test VFS implementation
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_vfs():
    from kos.filesystem.vfs import KOSVirtualFilesystem
    
    print("Testing VFS implementation...")
    
    # Create VFS (mock kernel)
    class MockKernel:
        pass
    
    vfs = KOSVirtualFilesystem(MockKernel())
    
    # Test basic directory operations
    print("Testing directory operations...")
    vfs.mkdir("/test")
    vfs.makedirs("/test/deep/nested/dirs")
    assert vfs.exists("/test")
    assert vfs.exists("/test/deep/nested/dirs")
    assert vfs.isdir("/test")
    print("✓ Directory operations work")
    
    # Test file operations
    print("Testing file operations...")
    vfs.create_file("/test/hello.txt", "Hello, KOS!")
    content = vfs.read_file("/test/hello.txt")
    assert content == "Hello, KOS!"
    assert vfs.isfile("/test/hello.txt")
    print("✓ File operations work")
    
    # Test listing
    print("Testing directory listing...")
    files = vfs.listdir("/test")
    assert "hello.txt" in files
    assert "deep" in files
    print("✓ Directory listing works")
    
    # Test symlinks
    print("Testing symlinks...")
    vfs.symlink("/test/hello.txt", "/test/link.txt")
    link_content = vfs.read_file("/test/link.txt")
    assert link_content == "Hello, KOS!"
    print("✓ Symlinks work")
    
    # Test permissions
    print("Testing permissions...")
    vfs.chmod("/test/hello.txt", 0o600)
    node = vfs.stat("/test/hello.txt")
    assert node.mode == 0o600
    print("✓ Permission changes work")
    
    print("All VFS tests passed!")

if __name__ == "__main__":
    test_vfs()
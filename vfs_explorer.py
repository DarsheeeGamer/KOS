#!/usr/bin/env python3
"""
KOS VFS Explorer - Standalone
==============================
Standalone tool for exploring the KOS Virtual File System from the host
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path

# Add KOS to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import KOS VFS
from kos.vfs import get_vfs
from kos.vfs.vfs_index import get_vfs_index

def explore_vfs():
    """Interactive VFS explorer"""
    
    # Initialize VFS
    vfs = get_vfs()
    if not vfs:
        print("Error: Could not initialize VFS")
        return 1
    
    # Get or create index
    index = get_vfs_index(vfs)
    
    print("\n" + "="*60)
    print("KOS VFS Explorer (kaede.kdsk)")
    print("="*60)
    
    # Show statistics
    stats = index.get_statistics()
    print(f"\nVFS Statistics:")
    print(f"  Total entries: {stats['total_entries']}")
    print(f"  Files: {stats['file_count']}")
    print(f"  Directories: {stats['directory_count']}")
    print(f"  Total size: {format_size(stats['total_size'])}")
    
    print("\nCommands: ls, cd, pwd, cat, tree, find, stat, help, exit")
    print()
    
    current_path = "/"
    
    while True:
        try:
            cmd_input = input(f"vfs:{current_path}> ").strip()
            
            if not cmd_input:
                continue
            
            parts = cmd_input.split()
            cmd = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            
            if cmd == 'exit' or cmd == 'quit':
                break
            
            elif cmd == 'help':
                show_help()
            
            elif cmd == 'pwd':
                print(current_path)
            
            elif cmd == 'ls':
                path = args[0] if args else current_path
                list_directory(index, path)
            
            elif cmd == 'cd':
                if not args:
                    current_path = "/"
                else:
                    new_path = resolve_path(current_path, args[0])
                    entry = index.get_entry(new_path)
                    if entry and entry.is_directory():
                        current_path = new_path
                    else:
                        print(f"Not a directory: {new_path}")
            
            elif cmd == 'cat':
                if args:
                    path = resolve_path(current_path, args[0])
                    cat_file(vfs, path)
                else:
                    print("Usage: cat <file>")
            
            elif cmd == 'tree':
                path = args[0] if args else current_path
                path = resolve_path(current_path, path)
                show_tree(index, path)
            
            elif cmd == 'find':
                pattern = args[0] if args else "*"
                find_files(index, pattern)
            
            elif cmd == 'stat':
                path = args[0] if args else current_path
                path = resolve_path(current_path, path)
                stat_file(index, path)
            
            else:
                print(f"Unknown command: {cmd}")
                print("Type 'help' for available commands")
                
        except KeyboardInterrupt:
            print("\nUse 'exit' to quit")
        except Exception as e:
            print(f"Error: {e}")
    
    return 0

def resolve_path(current, path):
    """Resolve a path relative to current directory"""
    if path.startswith('/'):
        return path
    elif path == '..':
        return os.path.dirname(current) or '/'
    elif path == '.':
        return current
    else:
        return os.path.join(current, path).replace('//', '/')

def format_size(size):
    """Format file size"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"

def list_directory(index, path):
    """List directory contents"""
    entries = index.list_directory(path)
    
    if not entries:
        # Try to check if it exists
        entry = index.get_entry(path)
        if not entry:
            print(f"Directory not found: {path}")
        elif not entry.is_directory():
            print(f"Not a directory: {path}")
        else:
            print("Directory is empty")
        return
    
    # Sort entries
    entries.sort(key=lambda e: (not e.is_directory(), e.name))
    
    # Display entries
    for entry in entries:
        if entry.is_directory():
            print(f"📁 {entry.name}/")
        else:
            size = format_size(entry.size)
            print(f"📄 {entry.name} ({size})")

def cat_file(vfs, path):
    """Display file contents"""
    try:
        import os
        VFS_O_RDONLY = os.O_RDONLY
        
        with vfs.open(path, VFS_O_RDONLY) as f:
            data = f.read()
            print(data.decode('utf-8', errors='replace'))
    except Exception as e:
        print(f"Cannot read file: {e}")

def show_tree(index, path, prefix="", max_depth=3, current_depth=0):
    """Display directory tree"""
    if current_depth == 0:
        entry = index.get_entry(path)
        if entry:
            print(f"📁 {path}")
        else:
            print(f"Not found: {path}")
            return
    
    if current_depth >= max_depth:
        return
    
    entries = index.list_directory(path)
    entries.sort(key=lambda e: (not e.is_directory(), e.name))
    
    for i, entry in enumerate(entries):
        is_last = (i == len(entries) - 1)
        connector = "└── " if is_last else "├── "
        
        if entry.is_directory():
            print(f"{prefix}{connector}📁 {entry.name}/")
            
            extension = "    " if is_last else "│   "
            child_path = os.path.join(path, entry.name).replace('//', '/')
            show_tree(index, child_path, prefix + extension, max_depth, current_depth + 1)
        else:
            size = format_size(entry.size)
            print(f"{prefix}{connector}📄 {entry.name} ({size})")

def find_files(index, pattern):
    """Find files matching pattern"""
    results = index.search(pattern)
    
    if not results:
        print(f"No files found matching '{pattern}'")
        return
    
    print(f"Found {len(results)} matches:")
    for entry in results[:20]:
        if entry.is_directory():
            print(f"  📁 {entry.path}/")
        else:
            print(f"  📄 {entry.path} ({format_size(entry.size)})")
    
    if len(results) > 20:
        print(f"  ... and {len(results) - 20} more")

def stat_file(index, path):
    """Show file statistics"""
    entry = index.get_entry(path)
    if not entry:
        print(f"Not found: {path}")
        return
    
    print(f"Path: {entry.path}")
    print(f"Type: {'Directory' if entry.is_directory() else 'File'}")
    print(f"Size: {format_size(entry.size)}")
    print(f"Mode: {oct(entry.mode)}")
    print(f"Modified: {time.ctime(entry.mtime)}")
    
    if entry.is_directory() and entry.children:
        print(f"Contains: {len(entry.children)} items")

def show_help():
    """Show help message"""
    print("\nVFS Explorer Commands:")
    print("="*40)
    print("ls [path]      - List directory contents")
    print("cd <path>      - Change directory")
    print("pwd            - Print working directory")
    print("cat <file>     - Display file contents")
    print("tree [path]    - Display directory tree")
    print("find <pattern> - Find files matching pattern")
    print("stat [path]    - Show file statistics")
    print("help           - Show this help")
    print("exit           - Exit explorer")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="KOS VFS Explorer - View kaede.kdsk contents")
    parser.add_argument('--stats', action='store_true',
                       help='Show VFS statistics and exit')
    parser.add_argument('--list', metavar='PATH',
                       help='List directory contents and exit')
    parser.add_argument('--tree', metavar='PATH',
                       help='Show directory tree and exit')
    
    args = parser.parse_args()
    
    if args.stats:
        # Just show stats
        vfs = get_vfs()
        if vfs:
            index = get_vfs_index(vfs)
            stats = index.get_statistics()
            print(f"KOS VFS Statistics (kaede.kdsk):")
            print(f"  Total entries: {stats['total_entries']}")
            print(f"  Files: {stats['file_count']}")
            print(f"  Directories: {stats['directory_count']}")
            print(f"  Total size: {format_size(stats['total_size'])}")
        return 0
    
    elif args.list:
        # List directory
        vfs = get_vfs()
        if vfs:
            index = get_vfs_index(vfs)
            list_directory(index, args.list)
        return 0
    
    elif args.tree:
        # Show tree
        vfs = get_vfs()
        if vfs:
            index = get_vfs_index(vfs)
            show_tree(index, args.tree)
        return 0
    
    else:
        # Interactive mode
        return explore_vfs()

if __name__ == "__main__":
    sys.exit(main())
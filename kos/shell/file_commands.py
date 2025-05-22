"""
Enhanced file operation commands for KOS shell
"""
import os
import re
import fnmatch
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from ..filesystem.base import FileSystem, FileNode
from ..exceptions import FileSystemError, FileNotFound, NotADirectory, IsADirectory

logger = logging.getLogger('KOS.shell.file_commands')

def touch_file(fs: FileSystem, path: str) -> Tuple[bool, str]:
    """
    Create a new empty file or update file timestamp if it exists
    
    Args:
        fs: The filesystem instance
        path: Path to the file to touch
        
    Returns:
        Tuple of (success, message)
    """
    try:
        abs_path = fs._resolve_path(path)
        parent_path = os.path.dirname(abs_path)
        file_name = os.path.basename(abs_path)
        
        # Get parent directory
        parent = fs._get_node(parent_path)
        if not parent:
            return False, f"Parent directory not found: {parent_path}"
        if parent.type != 'directory':
            return False, f"Parent path is not a directory: {parent_path}"
            
        node = fs._get_node(abs_path)
        if node:
            # File exists, update timestamp
            node.metadata['modified'] = datetime.now()
            return True, f"Updated timestamp for {path}"
        else:
            # Create new empty file
            if isinstance(parent.content, dict):
                new_file = FileNode(file_name, 'file', parent)
                parent.content[file_name] = new_file
                parent.metadata['modified'] = datetime.now()
                return True, f"Created new file: {path}"
            else:
                return False, f"Parent node content is not a dictionary: {parent_path}"
                
    except Exception as e:
        logger.error(f"Error in touch command: {e}")
        return False, f"Error: {str(e)}"

def find_files(fs: FileSystem, start_path: str, pattern: str = "*", max_depth: int = None) -> List[str]:
    """
    Find files matching a pattern recursively from a start path
    
    Args:
        fs: The filesystem instance
        start_path: Starting directory path
        pattern: File pattern to match (glob format)
        max_depth: Maximum recursion depth
        
    Returns:
        List of matching file paths
    """
    results = []
    
    try:
        abs_start = fs._resolve_path(start_path)
        start_node = fs._get_node(abs_start)
        
        if not start_node:
            return []
            
        if start_node.type != 'directory':
            return []
        
        def _find_recursive(current_path: str, node: FileNode, depth: int = 0):
            if max_depth is not None and depth > max_depth:
                return
                
            if node.type != 'directory' or not isinstance(node.content, dict):
                return
                
            for name, child in node.content.items():
                child_path = f"{current_path}/{name}" if current_path != '/' else f"/{name}"
                
                # Check if this child matches the pattern
                if fnmatch.fnmatch(name, pattern):
                    results.append(child_path)
                    
                # Recurse into directories
                if child.type == 'directory':
                    _find_recursive(child_path, child, depth + 1)
        
        # Start the recursive search
        _find_recursive(abs_start, start_node)
        return results
        
    except Exception as e:
        logger.error(f"Error in find command: {e}")
        return []

def grep_text(fs: FileSystem, pattern: str, path: str, case_sensitive: bool = True) -> List[Tuple[str, int, str]]:
    """
    Search for pattern in a file or directory of files
    
    Args:
        fs: The filesystem instance
        pattern: Text pattern to search for
        path: File or directory path to search in
        case_sensitive: Whether the search should be case sensitive
        
    Returns:
        List of tuples containing (file_path, line_number, line_content)
    """
    results = []
    regex_flags = 0 if case_sensitive else re.IGNORECASE
    
    try:
        # Compile regex pattern
        regex = re.compile(pattern, regex_flags)
        
        abs_path = fs._resolve_path(path)
        node = fs._get_node(abs_path)
        
        if not node:
            return []
            
        # Function to search in a single file
        def _search_file(file_path: str, file_node: FileNode):
            if not isinstance(file_node.content, str):
                return
                
            content = file_node.content
            lines = content.split('\n')
            
            for i, line in enumerate(lines):
                if regex.search(line):
                    results.append((file_path, i+1, line))
        
        # If path is a file, search that file
        if node.type == 'file':
            _search_file(abs_path, node)
        # If path is a directory, search all files in the directory
        elif node.type == 'directory' and isinstance(node.content, dict):
            for name, child in node.content.items():
                if child.type == 'file':
                    child_path = f"{abs_path}/{name}" if abs_path != '/' else f"/{name}"
                    _search_file(child_path, child)
        
        return results
        
    except Exception as e:
        logger.error(f"Error in grep command: {e}")
        return []

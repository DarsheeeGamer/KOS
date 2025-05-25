"""
KOS Filesystem Path Utilities

This module provides path handling utilities for the KOS filesystem,
including path normalization, resolution, and manipulation.
"""

import os
import re
import logging
from typing import List, Tuple, Optional, Dict

# Set up logging
logger = logging.getLogger('KOS.core.filesystem.path_utils')

# Constants
PATH_SEPARATOR = '/'
CURRENT_DIR = '.'
PARENT_DIR = '..'


def normalize_path(path: str) -> str:
    """
    Normalize a path by resolving '.' and '..' components and removing redundant separators
    
    Args:
        path: Path to normalize
    
    Returns:
        Normalized path
    """
    # Replace Windows-style path separators with Unix-style
    path = path.replace('\\', PATH_SEPARATOR)
    
    # Split path into components
    components = path.split(PATH_SEPARATOR)
    
    # Resolve '.' and '..' components
    result = []
    for component in components:
        if not component or component == CURRENT_DIR:
            continue
        elif component == PARENT_DIR:
            if result and result[-1] != PARENT_DIR:
                result.pop()
            else:
                result.append(PARENT_DIR)
        else:
            result.append(component)
    
    # Handle special case for root path
    if path.startswith(PATH_SEPARATOR):
        normalized = PATH_SEPARATOR + PATH_SEPARATOR.join(result)
    else:
        normalized = PATH_SEPARATOR.join(result)
    
    # Handle empty path
    if not normalized:
        normalized = CURRENT_DIR
    
    return normalized


def resolve_path(base_path: str, rel_path: str) -> str:
    """
    Resolve a relative path against a base path
    
    Args:
        base_path: Base path
        rel_path: Relative path
    
    Returns:
        Resolved absolute path
    """
    # If rel_path is already absolute, return it normalized
    if is_absolute_path(rel_path):
        return normalize_path(rel_path)
    
    # Join paths and normalize
    joined = join_path(base_path, rel_path)
    return normalize_path(joined)


def join_path(*paths: str) -> str:
    """
    Join multiple path components
    
    Args:
        paths: Path components to join
    
    Returns:
        Joined path
    """
    if not paths:
        return CURRENT_DIR
    
    # Filter out empty components
    filtered = [p for p in paths if p]
    
    if not filtered:
        return CURRENT_DIR
    
    # Join with path separator
    result = filtered[0]
    for path in filtered[1:]:
        # If the next component is absolute, it replaces the result
        if is_absolute_path(path):
            result = path
        else:
            # Otherwise, join with a separator unless result ends with one
            if result.endswith(PATH_SEPARATOR):
                result += path
            else:
                result += PATH_SEPARATOR + path
    
    return result


def split_path(path: str) -> Tuple[str, str]:
    """
    Split a path into directory and filename components
    
    Args:
        path: Path to split
    
    Returns:
        Tuple of (directory, filename)
    """
    # Normalize the path first
    path = normalize_path(path)
    
    # Find the last separator
    last_sep = path.rfind(PATH_SEPARATOR)
    
    if last_sep == -1:
        # No separator, the whole path is a filename
        return CURRENT_DIR, path
    elif last_sep == 0:
        # Root directory with a filename
        return PATH_SEPARATOR, path[1:]
    else:
        # Regular case
        return path[:last_sep], path[last_sep+1:]


def is_absolute_path(path: str) -> bool:
    """
    Check if a path is absolute
    
    Args:
        path: Path to check
    
    Returns:
        True if the path is absolute, False otherwise
    """
    return path.startswith(PATH_SEPARATOR)


def is_relative_path(path: str) -> bool:
    """
    Check if a path is relative
    
    Args:
        path: Path to check
    
    Returns:
        True if the path is relative, False otherwise
    """
    return not is_absolute_path(path)


def get_absolute_path(path: str, current_dir: str = None) -> str:
    """
    Get the absolute path for a given path
    
    Args:
        path: Path to convert
        current_dir: Current directory (for relative paths)
    
    Returns:
        Absolute path
    """
    if is_absolute_path(path):
        return normalize_path(path)
    
    if current_dir is None:
        current_dir = os.getcwd().replace('\\', PATH_SEPARATOR)
    
    return resolve_path(current_dir, path)


def get_parent_directory(path: str) -> str:
    """
    Get the parent directory of a path
    
    Args:
        path: Path to get parent of
    
    Returns:
        Parent directory path
    """
    # Normalize the path first
    path = normalize_path(path)
    
    # Split into directory and filename
    directory, _ = split_path(path)
    
    return directory


def get_path_components(path: str) -> List[str]:
    """
    Split a path into its components
    
    Args:
        path: Path to split
    
    Returns:
        List of path components
    """
    # Normalize the path first
    path = normalize_path(path)
    
    # Split by separator and filter out empty components
    components = [c for c in path.split(PATH_SEPARATOR) if c]
    
    # Handle absolute paths
    if path.startswith(PATH_SEPARATOR):
        components.insert(0, PATH_SEPARATOR)
    
    return components


def get_path_depth(path: str) -> int:
    """
    Get the depth of a path (number of components)
    
    Args:
        path: Path to measure
    
    Returns:
        Path depth
    """
    components = get_path_components(path)
    
    # Adjust for root path
    if components and components[0] == PATH_SEPARATOR:
        return len(components) - 1
    
    return len(components)


def is_subpath(parent: str, child: str) -> bool:
    """
    Check if a path is a subpath of another
    
    Args:
        parent: Parent path
        child: Child path
    
    Returns:
        True if child is a subpath of parent, False otherwise
    """
    # Normalize both paths
    parent = normalize_path(parent)
    child = normalize_path(child)
    
    # Ensure both paths are absolute or both are relative
    if is_absolute_path(parent) != is_absolute_path(child):
        return False
    
    # Add trailing separator if not present
    if not parent.endswith(PATH_SEPARATOR):
        parent += PATH_SEPARATOR
    
    return child.startswith(parent)

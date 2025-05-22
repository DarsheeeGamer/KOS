#!/usr/bin/env python3
"""
KOS API Documentation Generator

This script generates API documentation for KOS Python modules using mkdocstrings.
It creates markdown files in the docs/api directory that can be processed by MkDocs.
"""

import os
import sys
import inspect
import importlib
import pkgutil
from pathlib import Path
from typing import List, Dict, Any, Optional

# Configuration
MODULE_PATHS = ["kos"]  # List of module paths to document
OUTPUT_DIR = Path("docs/api")
TEMPLATE = """# {module_name} Module

::: {module_path}
    options:
      show_root_heading: true
      show_source: true
      show_bases: true
      show_submodules: true
      show_if_no_docstring: false
"""

def ensure_directory(directory: Path) -> None:
    """Ensure the output directory exists."""
    directory.mkdir(parents=True, exist_ok=True)

def get_module_docstring(module_path: str) -> str:
    """Get the docstring for a module."""
    try:
        module = importlib.import_module(module_path)
        return inspect.getdoc(module) or ""
    except ImportError:
        return ""

def generate_module_docs(module_path: str, output_dir: Path) -> None:
    """Generate documentation for a module and its submodules."""
    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        print(f"Error importing {module_path}: {e}", file=sys.stderr)
        return

    # Create a directory structure that matches the module path
    rel_path = Path(*module_path.split('.'))
    module_dir = output_dir / rel_path.parent
    ensure_directory(module_dir)

    # Generate the markdown file
    output_file = module_dir / f"{rel_path.name}.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(TEMPLATE.format(
            module_name=module_path,
            module_path=module_path
        ))
    print(f"Generated: {output_file}")

    # Recursively process submodules
    if hasattr(module, '__path__'):
        for _, name, is_pkg in pkgutil.iter_modules(module.__path__):
            if name != '__main__':
                full_path = f"{module_path}.{name}"
                generate_module_docs(full_path, output_dir)

def main():
    """Generate API documentation for all specified modules."""
    ensure_directory(OUTPUT_DIR)
    
    # Create a README for the API docs
    with open(OUTPUT_DIR / "README.md", 'w', encoding='utf-8') as f:
        f.write("""# KOS API Reference

This section contains the complete API reference for KOS modules.

## Available Modules

""")
        for module_path in MODULE_PATHS:
            f.write(f"- [{module_path}]({module_path}/README.md)\n")
    
    # Generate docs for each module path
    for module_path in MODULE_PATHS:
        generate_module_docs(module_path, OUTPUT_DIR)
    
    print("\nAPI documentation generation complete!")
    print(f"Run 'mkdocs serve' to view the documentation locally.")

if __name__ == "__main__":
    main()

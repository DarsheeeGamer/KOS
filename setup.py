#!/usr/bin/env python
"""
KOS - Kaede OS: A Python-based Operating System Simulation with Advanced System Utilities
"""
from setuptools import setup, find_packages
import os
import sys

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()
    
# Define required packages
required_packages = [
    "pydantic>=2.0.0",  # For data validation and settings management
    "psutil>=5.9.0",    # For system monitoring and resource tracking
    "requests>=2.28.0", # For network operations and API interactions
    "colorama>=0.4.5",  # For terminal color support
    "prompt_toolkit>=3.0.30", # For enhanced command-line interface
    "pyyaml>=6.0",      # For configuration file support
    "tabulate>=0.9.0",  # For formatted table output
    "tqdm>=4.64.0",     # For progress bars
    "watchdog>=2.1.9",  # For filesystem monitoring
    "rich>=13.5.0",     # For rich terminal output
    "cachetools>=5.5.2", # For caching functionality
    "cryptography>=44.0.2", # For security features
    "typing-extensions>=4.5.0", # For enhanced type hints
]

# Platform-specific dependencies
if sys.platform == 'win32':
    required_packages.append("pyreadline3>=3.4.1")  # Windows readline support

setup(
    name="kos-shell",
    version="1.0.0",
    author="DarsheeeGamer",
    author_email="cleaverdeath@gmail.com",
    description="A Python-based operating system simulation with advanced system utilities",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/DarsheeeGamer/KOS",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=required_packages,
    entry_points={
        'console_scripts': [
            'kos=kos.main:main',
        ],
    },
    include_package_data=True,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=[
        "psutil>=5.9.0",
        "requests>=2.27.0",
        "shlex>=0.0.3",
        "pyyaml>=6.0",
        "rich>=12.0.0",
        "colorama>=0.4.4",
    ],
    entry_points={
        "console_scripts": [
            "kos=kos.cli:main",
        ],
    },
    include_package_data=True,
)

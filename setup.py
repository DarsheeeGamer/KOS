#!/usr/bin/env python
"""
KOS - Python-based Operating System Simulation with Advanced System Utilities
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

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

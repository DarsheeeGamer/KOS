#!/usr/bin/env python3
"""
Setup script for hello_py
"""

from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="hello_py",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A KOS Python application",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/hello_py",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Environment :: Console",
        "Intended Audience :: Developers",
    ],
    python_requires=">=3.6",
    install_requires=[
        # Add your dependencies here
    ],
    entry_points={
        'console_scripts': [
            'hello_py=hello_py.main:main',
        ],
    },
)

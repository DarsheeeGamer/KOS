# Creating KOS Packages

This guide explains how to create, package, and distribute KOS packages.

## Package Structure

A basic KOS package has the following structure:

```
my_package/
├── package.json          # Package metadata (required)
├── README.md             # Package documentation
├── requirements.txt       # Python dependencies (optional)
├── src/                  # Source code directory
│   ├── __init__.py       # Package initialization
│   └── main.py           # Main package code
└── tests/                # Tests (optional)
    └── test_main.py
```

## Package Metadata

Create a `package.json` file with the following structure:

```json
{
  "name": "my-package",
  "version": "1.0.0",
  "description": "A brief description of your package",
  "author": "Your Name <your.email@example.com>",
  "license": "MIT",
  "entry_point": "src/main.py",
  "dependencies": [
    "other-kos-package>=1.0.0"
  ],
  "pip_requirements": [
    "requests>=2.25.0"
  ],
  "tags": ["cli", "utility"],
  "repository": {
    "type": "git",
    "url": "https://github.com/yourusername/my-package.git"
  }
}
```

### Required Fields

- `name`: Package name (lowercase, hyphens for spaces)
- `version`: Package version (following semantic versioning)
- `description`: Brief description of the package
- `entry_point`: Path to the main Python file (relative to package root)

### Optional Fields

- `author`: Package author
- `license`: Software license (MIT, GPL-3.0, etc.)
- `dependencies`: List of KOS package dependencies
- `pip_requirements`: List of Python package dependencies
- `tags`: List of tags for categorization
- `repository`: Source code repository information

## Creating a Simple Package

### 1. Set Up the Project Structure

```bash
mkdir -p my_package/src my_package/tests
cd my_package
```

### 2. Create package.json

```bash
cat > package.json << 'EOF'
{
  "name": "hello-kos",
  "version": "1.0.0",
  "description": "A simple hello world package for KOS",
  "author": "Your Name <your.email@example.com>",
  "license": "MIT",
  "entry_point": "src/main.py",
  "dependencies": [],
  "pip_requirements": ["rich"],
  "tags": ["example", "hello-world"]
}
EOF
```

### 3. Create the Main Module

```bash
mkdir -p src
cat > src/main.py << 'EOF'
#!/usr/bin/env python3
"""Hello World package for KOS."""

def main():
    """Print a friendly greeting."""
    print("Hello, KOS!")

if __name__ == "__main__":
    main()
EOF
```

### 4. Create a README.md

```bash
cat > README.md << 'EOF'
# Hello KOS

A simple hello world package for KOS.

## Installation

```bash
kpm install hello-kos
```

## Usage

```bash
hello-kos
```

## License

MIT
EOF
```

## Testing Your Package

### 1. Install in Development Mode

```bash
# From your package directory
pip install -e .
```

### 2. Run Tests

```bash
# Create a simple test
mkdir -p tests
cat > tests/test_hello.py << 'EOF'
import unittest
from src.main import main
from io import StringIO
import sys

class TestHello(unittest.TestCase):
    def test_main(self):
        captured_output = StringIO()
        sys.stdout = captured_output
        main()
        sys.stdout = sys.__stdout__
        self.assertIn("Hello, KOS!", captured_output.getvalue())

if __name__ == "__main__":
    unittest.main()
EOF

# Run tests
python -m pytest tests/
```

## Building a Package

### 1. Create a setup.py

```python
from setuptools import setup, find_packages

setup(
    name="hello-kos",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[],
    entry_points={
        'console_scripts': [
            'hello-kos=src.main:main',
        ],
    },
)
```

### 2. Build the Package

```bash
python setup.py sdist bdist_wheel
```

This will create a `dist/` directory containing your package files.

## Publishing Your Package

### 1. Create a KOS Repository

Create a new GitHub repository for your package and push your code:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/yourusername/hello-kos.git
git push -u origin main
```

### 2. Create a Release

1. Go to your repository on GitHub
2. Click on "Releases"
3. Click "Create a new release"
4. Enter a version tag (e.g., v1.0.0)
5. Add release notes
6. Upload your package files from the `dist/` directory
7. Click "Publish release"

## Advanced Package Features

### Including Data Files

To include non-Python files (like templates, configs):

1. Create a `MANIFEST.in` file:
   ```
   include README.md
   recursive-include src/data *
   ```

2. Update `setup.py`:
   ```python
   setup(
       # ...
       include_package_data=True,
       package_data={
           '': ['*.txt', '*.json', '*.yaml'],
       },
   )
   ```

### Entry Points

You can define multiple commands in your package:

```json
{
  "entry_points": {
    "console_scripts": [
      "hello-kos=src.main:main",
      "greet=src.greeter:greet"
    ]
  }
}
```

### Platform-Specific Dependencies

```json
{
  "dependencies": {
    "windows": ["windows-specific-package"],
    "linux": ["linux-specific-package"],
    "darwin": ["macos-specific-package"]
  },
  "pip_requirements": {
    "windows": ["pywin32"],
    "linux": ["dbus-python"],
    "darwin": ["pyobjc"]
  }
}
```

## Best Practices

1. **Versioning**: Follow [Semantic Versioning](https://semver.org/)
2. **Documentation**: Include a detailed README and docstrings
3. **Testing**: Write tests for your code
4. **Dependencies**: Keep them minimal and specify version ranges
5. **License**: Always include a license file
6. **Changelog**: Maintain a CHANGELOG.md file

## Example Packages

- [KOS Core Packages](https://github.com/DarsheeeGamer/KOS/tree/main/kos)
- [Example Package](https://github.com/example/example-kos-package)

## Next Steps

- [Package Metadata](./package-metadata.md) - Detailed guide on package metadata
- [Repository Management](./repository-management.md) - How to host your own KOS repository
- [API Reference](./api-reference/README.md) - KOS development APIs

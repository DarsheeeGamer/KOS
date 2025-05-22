# Package Metadata Reference

This document provides a comprehensive reference for the package metadata format used in KOS packages.

## Overview

Package metadata is defined in a `package.json` file at the root of your package. This file contains all the information needed to install, run, and manage your package.

## Metadata Fields

### Required Fields

#### `name` (string)
- The name of your package
- Must be lowercase and use hyphens for word separation
- Must be unique within the KOS ecosystem
- Example: `"name": "my-awesome-package"`

#### `version` (string)
- The version of your package
- Must follow [Semantic Versioning](https://semver.org/)
- Example: `"version": "1.0.0"`

#### `description` (string)
- A short description of what your package does
- Should be 1-2 sentences
- Example: `"description": "A package for managing todo lists in KOS"`

#### `entry_point` (string)
- Path to the main Python module that should be executed
- Relative to the package root
- Example: `"entry_point": "src/main.py"`

### Optional Fields

#### `author` (string or object)
- The package author's name and optionally email
- Can be a string: `"author": "John Doe <john@example.com>"`
- Or an object:
  ```json
  "author": {
    "name": "John Doe",
    "email": "john@example.com",
    "url": "https://example.com"
  }
  ```

#### `license` (string or object)
- The software license for the package
- Can be a string: `"license": "MIT"`
- Or an object with additional details:
  ```json
  "license": {
    "type": "MIT",
    "url": "https://opensource.org/licenses/MIT"
  }
  ```

#### `dependencies` (object)
- Other KOS packages that this package depends on
- Keys are package names, values are version constraints
- Example:
  ```json
  "dependencies": {
    "core-utils": ">=1.0.0",
    "file-manager": "^2.0.0"
  }
  ```

#### `pip_requirements` (array or object)
- Python package dependencies
- Can be a simple array:
  ```json
  "pip_requirements": ["requests>=2.25.0", "rich"]
  ```
- Or an object with platform-specific requirements:
  ```json
  "pip_requirements": {
    "all": ["requests>=2.25.0"],
    "windows": ["pywin32"],
    "linux": ["dbus-python"],
    "darwin": ["pyobjc"]
  }
  ```

#### `tags` (array of strings)
- Keywords to help categorize your package
- Used for discovery and filtering
- Example: `"tags": ["cli", "productivity", "todo"]`

#### `repository` (string or object)
- Where the source code is hosted
- Can be a URL string: `"repository": "https://github.com/username/repo"`
- Or an object with more details:
  ```json
  "repository": {
    "type": "git",
    "url": "https://github.com/username/repo.git",
    "directory": "packages/awesome"
  }
  ```

#### `homepage` (string)
- The URL to the project's homepage
- Example: `"homepage": "https://example.com/my-package"`

#### `bugs` (string or object)
- Where to report issues
- Example: `"bugs": "https://github.com/username/repo/issues"`
- Or with more details:
  ```json
  "bugs": {
    "url": "https://github.com/username/repo/issues",
    "email": "bugs@example.com"
  }
  ```

#### `keywords` (array of strings)
- Keywords that describe your package
- Used for search and discovery
- Example: `"keywords": ["kos", "productivity", "cli"]`

#### `os` (array of strings, optional)
- List of supported operating systems
- Example: `"os": ["linux", "darwin", "win32"]`

#### `cpu` (array of strings, optional)
- List of supported CPU architectures
- Example: `"cpu": ["x64", "arm64"]`

## Advanced Metadata

### Entry Points

Define additional commands and extensions:

```json
"entry_points": {
  "console_scripts": [
    "my-command=my_package.module:function"
  ],
  "kos.extensions": [
    "my_extension=my_package.ext:init_extension"
  ]
}
```

### Scripts

Define package lifecycle scripts:

```json
"scripts": {
  "preinstall": "echo 'About to install...'",
  "postinstall": "echo 'Installation complete!',
  "preuninstall": "echo 'Preparing to remove...'"
}
```

### Configuration

Define configuration options:

```json
"config": {
  "default_port": 8080,
  "log_level": "info"
}
```

## Example package.json

```json
{
  "name": "todo-manager",
  "version": "1.0.0",
  "description": "A simple todo list manager for KOS",
  "author": {
    "name": "Jane Smith",
    "email": "jane@example.com",
    "url": "https://example.com"
  },
  "license": "MIT",
  "entry_point": "src/main.py",
  "dependencies": {
    "core-utils": ">=1.0.0",
    "file-manager": "^2.0.0"
  },
  "pip_requirements": [
    "rich>=10.0.0",
    "python-dateutil>=2.8.0"
  ],
  "tags": ["cli", "productivity", "todo"],
  "repository": {
    "type": "git",
    "url": "https://github.com/username/todo-manager.git"
  },
  "homepage": "https://github.com/username/todo-manager",
  "bugs": "https://github.com/username/todo-manager/issues",
  "keywords": ["kos", "todo", "productivity", "cli"],
  "os": ["linux", "darwin", "win32"],
  "entry_points": {
    "console_scripts": [
      "todo=todo.cli:main"
    ]
  },
  "scripts": {
    "postinstall": "echo 'Todo manager installed successfully!'",
    "preuninstall": "echo 'Removing todo manager...'"
  },
  "config": {
    "default_editor": "nano",
    "auto_save": true
  }
}
```

## Version Constraints

KOS uses the same version constraint syntax as npm:

- `1.2.3`: Exact version
- `>1.2.3`: Greater than version
- `>=1.2.3`: Greater than or equal to
- `<1.2.3`: Less than
- `<=1.2.3`: Less than or equal to
- `~1.2.3`: Approximately equivalent to version (patch updates allowed)
- `^1.2.3`: Compatible with version (minor updates allowed)
- `1.2.x` or `1.x`: Version ranges
- `*`: Any version
- `https://...`: URL to a tarball
- `git+https://...`: Git repository URL

## Platform-Specific Dependencies

You can specify platform-specific dependencies:

```json
{
  "dependencies": {
    "core-utils": ">=1.0.0"
  },
  "optionalDependencies": {
    "windows": ["windows-utils"],
    "linux": ["linux-utils"],
    "darwin": ["darwin-utils"]
  }
}
```

## Best Practices

1. **Versioning**: Follow semantic versioning (MAJOR.MINOR.PATCH)
2. **Dependencies**: Keep them minimal and well-defined
3. **Documentation**: Include a detailed README.md
4. **Testing**: Include tests and document how to run them
5. **License**: Always include a license file
6. **Changelog**: Maintain a CHANGELOG.md file

## Validation

You can validate your package.json using:

```bash
kpm validate
```

This will check for required fields and validate the format.

## Next Steps

- [Creating Packages](./creating-packages.md) - How to create and package your application
- [Repository Management](./repository-management.md) - How to publish and share your package
- [API Reference](./api-reference/README.md) - KOS development APIs

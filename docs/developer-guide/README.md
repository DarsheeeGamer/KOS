# KOS Developer Guide

Welcome to the KOS Developer Guide! This guide provides comprehensive documentation for developers looking to extend, modify, or contribute to the KOS project.

## Table of Contents

1. [Getting Started with Development](./getting-started.md)
   - Setting up the development environment
   - Project structure
   - Building from source

2. [Creating Packages](./creating-packages.md)
   - Package structure
   - Writing package code
   - Including resources
   - Testing packages

3. [Package Metadata](./package-metadata.md)
   - Metadata format
   - Dependencies
   - Versioning
   - PIP requirements

4. [Repository Management](./repository-management.md)
   - Creating repositories
   - Hosting packages
   - Repository structure
   - Security considerations

5. [API Reference](./api-reference/README.md)
   - Core APIs
   - Extension points
   - Best practices

6. [Testing](./testing.md)
   - Writing tests
   - Running tests
   - Test coverage

7. [Debugging](./debugging.md)
   - Common issues
   - Debugging tools
   - Logging

8. [Contributing](./contributing.md)
   - Code style
   - Pull requests
   - Issue tracking

9. [Release Process](./release-process.md)
   - Versioning
   - Creating releases
   - Changelog management

## Getting Help

- [GitHub Issues](https://github.com/DarsheeeGamer/KOS/issues) - Report bugs and request features
- [Discussions](https://github.com/DarsheeeGamer/KOS/discussions) - Ask questions and discuss ideas
- [Contributing Guide](./contributing.md) - Learn how to contribute to KOS

## Development Environment

### Prerequisites

- Python 3.8+
- Git
- pip

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/DarsheeeGamer/KOS.git
   cd KOS
   ```

2. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

3. Install KOS in development mode:
   ```bash
   pip install -e .
   ```

## Building Documentation

Documentation is built using MkDocs with the Material theme.

```bash
# Install documentation dependencies
pip install mkdocs mkdocs-material

# Build and serve documentation
mkdocs serve
```

Visit http://127.0.0.1:8000 to view the documentation.

## Testing

Run the test suite:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=kos tests/
```

## Code Style

KOS follows the [PEP 8](https://www.python.org/dev/peps/pep-0008/) style guide. We use the following tools to maintain code quality:

- `black` for code formatting
- `flake8` for linting
- `isort` for import sorting

Run code formatting:

```bash
black .
isort .
```

## Contributing

We welcome contributions! Please see our [Contributing Guide](./contributing.md) for details on how to contribute to the project.

## License

KOS is licensed under the MIT License. See the [LICENSE](https://github.com/DarsheeeGamer/KOS/blob/main/LICENSE) file for details.

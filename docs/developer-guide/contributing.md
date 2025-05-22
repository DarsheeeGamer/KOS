# Contributing to KOS

Thank you for your interest in contributing to the KOS project! This guide will help you get started with contributing code, documentation, and more.

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Style](#code-style)
- [Documentation](#documentation)
- [Testing](#testing)
- [Pull Requests](#pull-requests)
- [Code Review](#code-review)
- [Reporting Issues](#reporting-issues)
- [Feature Requests](#feature-requests)
- [Community](#community)

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before contributing.

## Getting Started

### Prerequisites
- Python 3.8+
- Git
- Virtual environment (recommended)
- Basic understanding of the KOS architecture

### Setting Up Your Environment

1. **Fork the Repository**
   ```bash
   # Fork the repository on GitHub
   # Clone your fork
   git clone https://github.com/your-username/KOS.git
   cd KOS
   ```

2. **Set Up a Virtual Environment**
   ```bash
   # Create a virtual environment
   python -m venv venv
   
   # Activate the virtual environment
   # On Windows:
   .\venv\Scripts\activate
   # On Unix/macOS:
   source venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   # Install development dependencies
   pip install -r requirements-dev.txt
   
   # Install the package in development mode
   pip install -e .
   ```

4. **Run Tests**
   ```bash
   # Run all tests
   pytest
   
   # Run tests with coverage
   pytest --cov=kos tests/
   ```

## Development Workflow

### Branching Strategy
- `main`: Stable, production-ready code
- `develop`: Integration branch for features
- `feature/`: Feature branches (e.g., `feature/user-authentication`)
- `bugfix/`: Bug fix branches
- `release/`: Release preparation branches

### Creating a New Feature

1. **Create a new branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write code
   - Add tests
   - Update documentation

3. **Commit your changes**
   ```bash
   # Stage changes
   git add .
   
   # Commit with a descriptive message
   git commit -m "Add your feature description"
   ```

4. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

5. **Create a Pull Request**
   - Go to the KOS repository on GitHub
   - Click "New Pull Request"
   - Select your branch
   - Fill in the PR template
   - Request reviews from maintainers

## Code Style

### Python
- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use type hints for all new code
- Keep functions small and focused
- Write docstrings for all public functions/classes
- Use absolute imports

### Formatting
- Line length: 88 characters (Black default)
- Use double quotes for strings
- Sort imports using isort

### Pre-commit Hooks
We use pre-commit to enforce code style. Install it with:

```bash
# Install pre-commit
pip install pre-commit

# Install git hooks
pre-commit install
```

The following hooks are configured:
- Black (code formatting)
- isort (import sorting)
- flake8 (linting)
- mypy (type checking)
- pytest (run tests)

## Documentation

### Docstrings
Use Google style docstrings:

```python
def example_function(param1: str, param2: int) -> bool:
    """Short description of the function.

    Longer description with more details about the function's
    functionality and any important notes.

    Args:
        param1: Description of the first parameter.
        param2: Description of the second parameter.

    Returns:
        Description of the return value.

    """
    return True
```

### Documentation Site
To build the documentation locally:

```bash
# Install documentation dependencies
pip install -r docs/requirements.txt

# Build the documentation
cd docs
make html

# View the documentation
open _build/html/index.html
```

## Testing

### Writing Tests
- Write tests for all new features and bug fixes
- Follow the "Arrange-Act-Assert" pattern
- Use descriptive test names
- Keep tests independent and isolated
- Mock external dependencies

### Running Tests
```bash
# Run all tests
pytest

# Run a specific test file
pytest tests/test_module.py

# Run tests with coverage
pytest --cov=kos --cov-report=html
```

## Pull Requests

### PR Guidelines
- Keep PRs small and focused
- Include tests for new features
- Update documentation as needed
- Reference related issues
- Follow the PR template

### PR Template
```markdown
## Description

Brief description of the changes in this PR.

## Related Issues

- Fixes #issue_number
- Related to #issue_number

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)

## Checklist

- [ ] My code follows the style guidelines of this project
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
```

## Code Review

### Review Process
1. Create a draft PR for early feedback
2. Request reviews from relevant team members
3. Address all review comments
4. Make sure all tests pass
5. Get approval from at least one maintainer
6. Squash and merge when ready

### Review Guidelines
- Be constructive and respectful
- Focus on the code, not the person
- Suggest improvements, not just point out issues
- Acknowledge good practices
- Keep feedback actionable

## Reporting Issues

### Bug Reports
When reporting a bug, please include:
1. A clear, descriptive title
2. Steps to reproduce the issue
3. Expected behavior
4. Actual behavior
5. Environment details (OS, Python version, etc.)
6. Error messages or logs
7. Any relevant screenshots

### Security Issues
Please report security issues to security@kos.org instead of creating a public issue.

## Feature Requests

### Submitting a Feature Request
1. Check if the feature has been requested before
2. Describe the feature in detail
3. Explain why this feature would be valuable
4. Provide any relevant examples or use cases

## Community

### Getting Help
- Join our [Discord server](https://discord.gg/kos)
- Check the [FAQ](docs/faq.md)
- Search the [issue tracker](https://github.com/DarsheeeGamer/KOS/issues)

### Community Guidelines
- Be respectful and inclusive
- Help others when you can
- Follow the code of conduct
- Give credit where credit is due

## License
By contributing to KOS, you agree that your contributions will be licensed under the [MIT License](LICENSE).

## Acknowledgments
- Thank you to all our contributors
- Special thanks to our core maintainers
- Inspired by [list of inspirations]

## See Also
- [Developer Guide](./developer-guide/README.md)
- [Code of Conduct](./CODE_OF_CONDUCT.md)
- [License](./LICENSE)

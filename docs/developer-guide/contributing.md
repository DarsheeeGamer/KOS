# Contributing to KOS

Thank you for your interest in contributing to KOS! This guide will help you get started with contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
  - [Reporting Bugs](#reporting-bugs)
  - [Suggesting Enhancements](#suggesting-enhancements)
  - [Your First Code Contribution](#your-first-code-contribution)
  - [Pull Requests](#pull-requests)
- [Styleguides](#styleguides)
  - [Git Commit Messages](#git-commit-messages)
  - [Python Styleguide](#python-styleguide)
  - [Documentation Styleguide](#documentation-styleguide)
- [Development Workflow](#development-workflow)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Code Review Process](#code-review-process)
- [Community](#community)

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check [this list](#before-submitting-a-bug-report) as you might find out that you don't need to create one. When you are creating a bug report, please [include as many details as possible](#how-do-i-submit-a-good-bug-report).

### Suggesting Enhancements

Enhancement suggestions are tracked as [GitHub issues](https://guides.github.com/features/issues/).

### Your First Code Contribution

#### Local Development

1. Fork the repository
2. Clone your fork locally
3. Create a branch for your changes
4. Make your changes
5. Run tests
6. Push your changes to your fork
7. Open a pull request

### Pull Requests

1. Update the README.md with details of changes if needed
2. Add tests if applicable
3. Ensure the test suite passes
4. Make sure your code lints
5. Issue the pull request

## Styleguides

### Git Commit Messages

- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit the first line to 72 characters or less
- Reference issues and pull requests liberally
- Consider starting the commit message with an applicable emoji:
  - 🎨 `:art:` when improving the format/structure of the code
  - 🐎 `:racehorse:` when improving performance
  - 🚱 `:non-potable_water:` when plugging memory leaks
  - 📝 `:memo:` when writing docs
  - 🐛 `:bug:` when fixing a bug
  - 🔥 `:fire:` when removing code or files
  - 💚 `:green_heart:` when fixing the CI build
  - ✅ `:white_check_mark:` when adding tests
  - 🔒 `:lock:` when dealing with security
  - ⬆️ `:arrow_up:` when upgrading dependencies
  - ⬇️ `:arrow_down:` when downgrading dependencies

### Python Styleguide

All Python code must follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) and [PEP 257](https://www.python.org/dev/peps/pep-0257/) (docstring conventions).

### Documentation Styleguide

- Use [Markdown](https://daringfireball.net/projects/markdown/).
- Reference methods and classes in markdown with the custom `{}` notation:
  - Reference classes with `{ClassName}`
  - Reference instance methods with `{ClassName::methodName()}`
  - Reference class methods with `{ClassName.methodName()}`

## Development Workflow

1. Create a branch for your changes
2. Make your changes
3. Run tests
4. Update documentation if needed
5. Push to your fork and submit a pull request

## Project Structure

```
kos/
├── kos/                    # Main package
│   ├── __init__.py         # Package initialization
│   ├── shell/              # Shell implementation
│   ├── filesystem/         # Filesystem abstraction
│   ├── package/            # Package management
│   └── process/            # Process management
├── tests/                  # Test suite
├── docs/                   # Documentation
└── scripts/                # Utility scripts
```

## Testing

Run the test suite:

```bash
pytest
```

Run tests with coverage:

```bash
pytest --cov=kos tests/
```

## Code Review Process

1. Automated tests run on all pull requests
2. At least one maintainer must review the changes
3. All CI checks must pass before merging
4. Squash and merge pull requests with a clear commit message

## Community

- [GitHub Discussions](https://github.com/yourusername/kos/discussions)
- [Discord/Slack Channel]
- [Mailing List]

## License

By contributing to KOS, you agree that your contributions will be licensed under its MIT License.

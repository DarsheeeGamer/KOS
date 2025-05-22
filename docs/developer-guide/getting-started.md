# Getting Started with KOS Development

This guide will help you set up your development environment and get started with KOS development.

## Prerequisites

- Python 3.8 or higher
- Git
- pip (Python package manager)
- Basic understanding of Python programming

## Setting Up the Development Environment

### 1. Clone the Repository

```bash
git clone https://github.com/DarsheeeGamer/KOS.git
cd KOS
```

### 2. Create and Activate a Virtual Environment (Recommended)

On Windows:
```bash
python -m venv venv
.\venv\Scripts\activate
```

On Unix/macOS:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development dependencies
```

### 4. Install KOS in Development Mode

```bash
pip install -e .
```

## Project Structure

```
KOS/
├── kos/                    # Main package directory
│   ├── __init__.py         # Package initialization
│   ├── commands/           # Command implementations
│   ├── core/               # Core functionality
│   ├── package_manager/    # Package management
│   ├── shell/              # Shell implementation
│   └── utils/              # Utility functions
├── docs/                   # Documentation
├── tests/                  # Test suite
├── kos_packages.json       # Installed packages database
├── main.py                 # Entry point
└── requirements.txt        # Project dependencies
```

## Running KOS

### Development Mode

```bash
python main.py
```

### Debug Mode

```bash
python main.py --debug
```

### Running Tests

Run the full test suite:

```bash
pytest
```

Run a specific test file:

```bash
pytest tests/test_module.py
```

Run tests with coverage:

```bash
pytest --cov=kos tests/
```

## Development Workflow

1. **Create a new branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Follow the [code style guide](#code-style)
   - Write tests for new features
   - Update documentation as needed

3. **Run tests**
   ```bash
   pytest
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "Add your commit message"
   ```

5. **Push to GitHub**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create a Pull Request**
   - Go to the KOS repository on GitHub
   - Click "New Pull Request"
   - Select your branch
   - Fill in the PR template
   - Submit the PR

## Code Style

KOS follows the [PEP 8](https://www.python.org/dev/peps/pep-0008/) style guide. We use the following tools to maintain code quality:

- `black` for code formatting
- `flake8` for linting
- `isort` for import sorting

### Formatting Code

Before committing, run:

```bash
black .
isort .
```

### Linting

```bash
flake8
```

## Documentation

### Building Documentation

```bash
cd docs
pip install -r requirements-docs.txt
mkdocs serve
```

Then open http://127.0.0.1:8000 in your browser.

### Writing Documentation

- Use Markdown for all documentation
- Follow the existing style and format
- Include code examples where helpful
- Keep documentation up-to-date with code changes

## Debugging

### Debug Mode

Run KOS in debug mode for more verbose output:

```bash
python main.py --debug
```

### Logging

Logs are stored in `kos.log` by default. You can view them with:

```bash
tail -f kos.log
```

## Next Steps

- [Creating Packages](./creating-packages.md) - Learn how to create and package KOS applications
- [API Reference](./api-reference/README.md) - Explore the KOS APIs
- [Contributing](./contributing.md) - Learn how to contribute to KOS

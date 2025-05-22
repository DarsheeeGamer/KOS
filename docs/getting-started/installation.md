# Installation Guide

This guide will walk you through installing KOS on your system.

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git (for development installations)

## Installation Methods

### Method 1: From Source (Recommended for Developers)

1. Clone the repository:
   ```bash
   git clone https://github.com/DarsheeeGamer/KOS.git
   cd KOS
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run KOS:
   ```bash
   python main.py
   ```

### Method 2: Using pip (Coming Soon)

```bash
pip install kos-shell
kos
```

## First Run

On first run, KOS will:
1. Create necessary configuration files
2. Set up the default user (username: `kaede`)
3. Initialize the package manager

## Updating KOS

To update an existing installation:

```bash
cd /path/to/KOS
git pull
pip install -r requirements.txt
```

## Troubleshooting

### Common Issues

1. **Missing Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Permission Issues**:
   - On Unix/Linux/macOS, you might need to use `sudo` for installation
   - On Windows, run the command prompt as Administrator

3. **Python Version**:
   Ensure you're using Python 3.8 or higher:
   ```bash
   python --version
   ```

## Next Steps

- [First Steps](./first-steps.md) - Learn the basics of using KOS
- [User Guide](../user-guide/README.md) - Comprehensive usage documentation
- [Developer Guide](../developer-guide/README.md) - Information for developers

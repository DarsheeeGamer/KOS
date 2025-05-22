# KOS Installation Guide

This guide provides comprehensive instructions for installing KOS (Kernel Operating System) on various platforms.

## Table of Contents
- [System Requirements](#system-requirements)
- [Installation Methods](#installation-methods)
  - [Linux](#linux-installation)
  - [Windows](#windows-installation)
  - [macOS](#macos-installation)
  - [Docker](#docker-installation)
- [Post-Installation](#post-installation)
- [Updating KOS](#updating-kos)
- [Troubleshooting](#troubleshooting)
- [Uninstallation](#uninstallation)

## System Requirements

### Minimum Requirements
- **Processor**: 64-bit x86_64 or ARM64
- **Memory**: 2GB RAM (4GB recommended)
- **Storage**: 10GB free disk space
- **Python**: 3.8 or higher
- **pip**: Latest version
- **Git**: For source installations

### Supported Platforms
- **Linux**: Ubuntu 20.04+, Debian 10+, Fedora 33+, CentOS 8+
- **Windows**: 10/11 (64-bit)
- **macOS**: 10.15 (Catalina) or later
- **Docker**: Any platform with Docker Engine

## Installation Methods

### Linux Installation

#### From Source (Recommended for Development)

1. **Install Dependencies**
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install -y python3-pip python3-venv git build-essential
   
   # Fedora
   sudo dnf install -y python3-pip python3-virtualenv git @development-tools
   
   # CentOS/RHEL 8+
   sudo dnf install -y python38 python38-pip python38-virtualenv git @development-tools
   ```

2. **Clone the Repository**
   ```bash
   git clone https://github.com/DarsheeeGamer/KOS.git
   cd KOS
   ```

3. **Create and Activate Virtual Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

4. **Install Dependencies**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

5. **Verify Installation**
   ```bash
   python -m kos --version
   ```

#### Using Package Manager (Coming Soon)
```bash
# For Ubuntu/Debian
sudo apt-add-repository ppa:kos/release
sudo apt update
sudo apt install kos

# For Fedora
sudo dnf install kos
```

### Windows Installation

#### Using Python

1. **Install Python**
   - Download Python 3.8+ from [python.org](https://www.python.org/downloads/windows/)
   - During installation, check "Add Python to PATH"

2. **Install Git**
   - Download and install Git from [git-scm.com](https://git-scm.com/download/win)

3. **Open Command Prompt**
   ```cmd
   git clone https://github.com/DarsheeeGamer/KOS.git
   cd KOS
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

#### Using Windows Package Manager (Coming Soon)
```powershell
winget install KOS.KOS
```

### macOS Installation

#### Using Homebrew (Recommended)
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install KOS
brew install kos
```

#### From Source
```bash
# Install Xcode Command Line Tools
xcode-select --install

# Clone and install
brew install python@3.9 git
pip3 install --upgrade pip
pip3 install -r requirements.txt
```

### Docker Installation

#### Quick Start
```bash
docker run -it darsheeegamer/kos:latest
```

#### Building from Source
```bash
git clone https://github.com/DarsheeeGamer/KOS.git
cd KOS
docker build -t kos .
docker run -it kos
```

## Post-Installation

### First Run
On first launch, KOS will:
1. Create configuration files in `~/.kos/`
2. Set up the default user
3. Initialize the package manager

### Configuration
Edit the config file at `~/.kos/config.yaml` to customize settings:

```yaml
# Example configuration
user:
  name: "admin"
  shell: "/bin/bash"
  home: "/home/admin"

network:
  hostname: "kos-system"
  dns_servers: ["8.8.8.8", "1.1.1.1"]
```

### Adding to PATH (Optional)
To run KOS from anywhere:

```bash
# Linux/macOS
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Windows (PowerShell)
[Environment]::SetEnvironmentVariable("Path", 
    [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::User) + 
    ";$env:APPDATA\Python\Python39\Scripts", 
    [EnvironmentVariableTarget]::User)
```

## Updating KOS

### From Source
```bash
cd /path/to/KOS
git pull
pip install -r requirements.txt --upgrade
```

### Using Package Manager
```bash
# Linux (apt)
sudo apt update && sudo apt upgrade kos

# macOS (Homebrew)
brew update && brew upgrade kos
```

## Troubleshooting

### Common Issues

#### Python Version Issues
```bash
# Check Python version
python3 --version

# If multiple versions are installed, use specific version
python3.9 -m pip install -r requirements.txt
```

#### Permission Denied
```bash
# Fix permission issues
chmod +x scripts/*
sudo chown -R $(whoami) /usr/local/
```

#### Missing Dependencies
```bash
# On Ubuntu/Debian
sudo apt-get install -y python3-dev libffi-dev libssl-dev

# On Fedora
sudo dnf install -y python3-devel libffi-devel openssl-devel
```

## Uninstallation

### From Source
```bash
# Remove the KOS directory
rm -rf /path/to/KOS

# Remove configuration files
rm -rf ~/.kos
```

### Using Package Manager
```bash
# Linux (apt)
sudo apt remove --purge kos

# macOS (Homebrew)
brew uninstall kos
brew autoremove
```

## Getting Help

If you encounter any issues:
1. Check the [Troubleshooting Guide](#troubleshooting)
2. Search the [GitHub Issues](https://github.com/DarsheeeGamer/KOS/issues)
3. [Open a New Issue](https://github.com/DarsheeeGamer/KOS/issues/new/choose)

## Next Steps

After installation, you might want to:
1. [Take the First Steps](../getting-started/first-steps.md)
2. [Learn Basic Commands](../user-guide/basic-commands.md)
3. [Configure Your Environment](../user-guide/environment-vars.md)
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

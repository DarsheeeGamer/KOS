# KOS - Kaede Operating System v2.0

A clean, modular virtual operating system written in Python with a complete Virtual File System.

## 🚀 Quick Start

```bash
# Clone and run
git clone https://github.com/DarsheeeGamer/KOS.git
cd KOS
python3 main.py
```

## ✨ Features

- **Virtual File System (VFS)** - Complete filesystem in `kaede.kdsk`
- **KLayer** - Core OS services (processes, services, networking)  
- **KADVLayer** - Advanced features (monitoring, security, containers)
- **KPM** - Package manager with dependency resolution
- **Python VFS** - Install Python packages entirely in VFS
- **Clean Shell** - Single, working shell with modular commands

## 📦 Architecture

```
KOS/
├── main.py              # Entry point
├── kaede.kdsk          # VFS disk image
└── kos/
    ├── core/           # VFS, config, errors
    ├── layers/         # KLayer & KADVLayer
    ├── packages/       # KPM & Python environment
    └── shell/          # Interactive shell
        └── commands/   # Modular commands
```

## 🎮 Usage

### Basic Commands

```bash
# File operations
ls              # List directory
cd <dir>        # Change directory
pwd             # Print working directory
cat <file>      # Display file
mkdir <dir>     # Create directory
touch <file>    # Create file
rm <file>       # Remove file
cp <src> <dst>  # Copy file
mv <src> <dst>  # Move file

# Package management
kpm list        # List packages
kpm install <package>    # Install package
kpm uninstall <package>  # Uninstall package
kpm search <query>       # Search packages

# Python packages (VFS)
pip install <package>    # Install to VFS
pip list                 # List VFS packages
pip uninstall <package>  # Uninstall from VFS

# System
status          # System status
info            # System information
ps              # List processes
services        # List services
monitor         # Performance metrics
container list  # List containers
```

### Command Line Options

```bash
python3 main.py                    # Interactive shell
python3 main.py -c "ls /"         # Run single command
python3 main.py --status           # Show status
python3 main.py --clean            # Start with fresh VFS
python3 main.py -v                 # Verbose mode
python3 main.py --version          # Show version
```

## 🏗️ Core Components

### VFS (Virtual File System)
- Complete Unix-like filesystem structure
- Stored in single `kaede.kdsk` file
- Supports files, directories, permissions
- No host filesystem pollution

### KLayer (Core OS Layer)
- Process management
- Service management
- System information
- Basic networking

### KADVLayer (Advanced Layer)
- Security monitoring
- Performance metrics
- Container management
- Firewall rules
- VPN connections

### KPM (Package Manager)
- Install/uninstall packages
- Dependency resolution
- Package search
- Version management

### Python VFS Environment
- Install Python packages to VFS
- Complete isolation from host
- PyPI integration
- Wheel support

## 🛠️ Development

### Project Structure
- **Clean Architecture**: ~3,000 lines vs previous 50,000+
- **Single Responsibility**: Each module does one thing well
- **No Global State**: Proper dependency injection
- **Modular Commands**: Easy to extend shell

### Adding Commands
Create new command module in `kos/shell/commands/`:

```python
def register_commands(shell):
    def do_mycommand(self, arg):
        """Command help text"""
        # Implementation
    
    shell.do_mycommand = do_mycommand
```

## 📝 What's Different in v2.0?

### Before (v1.0)
- 87 manager classes
- 5 different shells
- 4 package managers
- 50,000+ lines of broken code
- Dead files like `package_manager_broken.py`

### After (v2.0)
- Clean modular architecture
- Single working implementation of each component
- ~3,000 lines of working code
- Actually stores everything in VFS
- No fake features

## 🔧 Requirements

- Python 3.8+
- No external dependencies (pure Python)
- Works on Linux, macOS, Windows

## 📄 License

MIT License - See LICENSE file

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Write clean, working code
4. Test thoroughly
5. Submit pull request

## 🐛 Known Issues

- VFS currently uses pickle (will migrate to SQLite)
- Container feature is simplified simulation
- No real network isolation

## 🚦 Roadmap

- [ ] SQLite-based VFS backend
- [ ] Real process isolation
- [ ] Network namespace support
- [ ] GUI file manager
- [ ] Package repository hosting

## 💬 Support

Report issues: https://github.com/DarsheeeGamer/KOS/issues

---

**KOS v2.0** - Built from scratch with clean, working code.
"""KOS Documentation System"""
from typing import Dict, Optional

class ManualSystem:
    def __init__(self):
        self.pages: Dict[str, str] = {
            "kos": """
KOS (Kaede Operating System) - A Python-based Linux-like OS simulation

DESCRIPTION
    KOS is a comprehensive CLI-based operating system simulation that provides:
    - Package management (kapp)
    - File system operations
    - Process management
    - Network simulation
    - User management

COMMANDS
    Type 'help' to see available commands
    Use 'man <command>' for specific command documentation
""",
            "users": """
KOS User Management

DESCRIPTION
    KOS implements a full user management system with:
    - Root user (kaede)
    - User authentication
    - Group permissions
    - Home directories

COMMANDS
    useradd     Create a new user
    userdel     Delete a user
    su          Switch user
    whoami      Show current user
    groups      Show user groups
    id          Show user/group IDs
""",
            "filesystem": """
KOS File System

DESCRIPTION
    The KOS file system simulates a Unix-like hierarchical structure with:
    - Inodes for file metadata
    - Directory hierarchy
    - File permissions
    - Links support

COMMANDS
    ls      List directory contents
    cd      Change directory
    mkdir   Create directory
    touch   Create empty file
    rm      Remove file or directory
    cp      Copy files
    mv      Move/rename files
    chmod   Change file permissions
    chown   Change file ownership
""",
            "kapp": """
KOS Package Manager (KPM)

SYNOPSIS
    kapp <command> [options]

COMMANDS
    update              Update package lists from repositories
    install <pkg>       Install a package
    remove <pkg>        Remove a package
    list               List installed packages
    search <query>     Search for packages
    add-repo <url>     Add a new repository
    remove-repo <name> Remove a repository
    enable-repo <name> Enable a repository
    disable-repo <name> Disable a repository

PACKAGE CREATION
    To create a KOS package:
    1. Create a directory with your package name
    2. Add a kos_package.json file with metadata:
       {
         "name": "your_package",
         "version": "1.0.0",
         "description": "Package description",
         "author": "Your Name",
         "dependencies": ["dep1", "dep2"],
         "entry_point": "main.py"
       }
    3. Add your package files
    4. Test locally with: kapp install ./your_package

REPOSITORY CREATION
    To create a KOS package repository:
    1. Create a directory structure:
       repo/
       ├── packages/
       │   └── package_name/
       │       ├── versions/
       │       │   └── 1.0.0/
       │       │       ├── package_files
       │       │       └── kos_package.json
       └── index.json

    2. Generate repository index:
       {
         "name": "your_repo",
         "description": "Repository description",
         "packages": {
           "package_name": {
             "versions": ["1.0.0"],
             "latest": "1.0.0"
           }
         }
       }

    3. Host the repository (e.g., GitHub Pages)
    4. Add to KOS: kapp add-repo your_repo https://your-repo-url
""",
            "processes": """
KOS Process Management

DESCRIPTION
    KOS simulates process management with:
    - Process listing (ps)
    - Process monitoring (top)
    - Process control (kill, nice)
    - Resource usage tracking

COMMANDS
    ps      Show process status
    top     Display system tasks
    kill    Terminate processes
    nice    Adjust process priority
""",
            "network": """
KOS Network Tools

DESCRIPTION
    Network utilities included in KOS:
    - ICMP echo request (ping)
    - Network connections (netstat)
    - File transfer (wget, curl)

COMMANDS
    ping        Send ICMP ECHO_REQUEST
    netstat     Show network connections
    wget        Download files
    curl        Transfer data with URLs
"""
        }

    def get_page(self, topic: str) -> Optional[str]:
        """Get manual page content for a topic"""
        return self.pages.get(topic.lower())

    def add_page(self, topic: str, content: str):
        """Add or update a manual page"""
        self.pages[topic.lower()] = content

    def list_topics(self) -> list[str]:
        """List all available manual pages"""
        return sorted(self.pages.keys())
# Package Management in KOS

KOS Package Manager (kpm) is a powerful tool for managing software packages in KOS. It handles installation, removal, and updating of packages and their dependencies.

## Table of Contents

- [Package Management Basics](#package-management-basics)
- [Package Sources](#package-sources)
- [Managing Packages](#managing-packages)
  - [Installing Packages](#installing-packages)
  - [Removing Packages](#removing-packages)
  - [Updating Packages](#updating-packages)
  - [Listing Packages](#listing-packages)
  - [Searching for Packages](#searching-for-packages)
- [PIP Dependencies](#pip-dependencies)
- [Repository Management](#repository-management)
- [Package Metadata](#package-metadata)
- [Troubleshooting](#troubleshooting)

## Package Management Basics

KOS uses a centralized package management system that handles:
- Software installation and removal
- Dependency resolution
- Version management
- Repository management

## Package Sources

Packages can be installed from:
1. **Official KOS Repository** - Curated collection of verified packages
2. **Third-party Repositories** - Additional repositories can be added
3. **Local Files** - Install packages from local .kos files

## Managing Packages

### Installing Packages

To install a package:
```bash
kpm install <package_name>
```

Install a specific version:
```bash
kpm install <package_name>=<version>
```

Install from a local file:
```bash
kpm install /path/to/package.kos
```

### Removing Packages

To remove a package:
```bash
kpm remove <package_name>
```

Remove unused dependencies:
```bash
kpm autoremove
```

### Updating Packages

Update package lists:
```bash
kpm update
```

Upgrade all installed packages:
```bash
kpm upgrade
```

Upgrade a specific package:
```bash
kpm upgrade <package_name>
```

### Listing Packages

List installed packages:
```bash
kpm list
```

List available updates:
```bash
kpm list --upgradable
```

List files in a package:
```bash
kpm list-files <package_name>
```

### Searching for Packages

Search for a package:
```bash
kpm search <query>
```

Show package information:
```bash
kpm show <package_name>
```

## PIP Dependencies

KOS supports Python package dependencies through pip. These can be specified in the package metadata.

### Specifying PIP Dependencies

In the package's `index.json`:
```json
{
  "name": "myapp",
  "version": "1.0.0",
  "pip_requirements": [
    "rich",
    "requests>=2.25.0",
    "numpy"
  ]
}
```

### How PIP Dependencies Work

1. When a package is installed, KPM checks for `pip_requirements`
2. Each requirement is installed using `pip install`
3. Dependencies are installed in the system Python environment
4. Installation continues even if pip installation fails (with a warning)

### Managing PIP Dependencies

View installed pip packages:
```bash
kpm pip list
```

Install a pip package directly:
```bash
kpm pip install <package>
```

Remove a pip package:
```bash
kpm pip uninstall <package>
```

## Repository Management

### Adding Repositories

Add a repository:
```bash
kpm repo add <name> <url>
```

Example:
```bash
kpm repo add kos-extras https://example.com/kos-extras/
```

### Listing Repositories

List all repositories:
```bash
kpm repo list
```

### Enabling/Disabling Repositories

Enable a repository:
```bash
kpm repo enable <name>
```

Disable a repository:
```bash
kpm repo disable <name>
```

### Removing Repositories

Remove a repository:
```bash
kpm repo remove <name>
```

## Package Metadata

Package metadata is stored in `index.json` files. Common fields include:

```json
{
  "name": "package-name",
  "version": "1.0.0",
  "description": "Package description",
  "author": "Author Name",
  "repository": "https://example.com/repo",
  "entry_point": "main.py",
  "dependencies": [
    "other-package>=1.0.0"
  ],
  "pip_requirements": [
    "rich",
    "requests>=2.25.0"
  ],
  "tags": ["cli", "utility"],
  "license": "MIT"
}
```

## Troubleshooting

### Common Issues

1. **Dependency Resolution Failed**
   ```bash
   kpm install --fix-broken
   ```

2. **Package Not Found**
   - Check repository is enabled: `kpm repo list`
   - Update package lists: `kpm update`

3. **Permission Denied**
   - Run with elevated privileges: `sudo kpm install <package>`

4. **PIP Installation Failed**
   - Check internet connection
   - Try updating pip: `kpm pip install --upgrade pip`
   - Install with `--user` flag if needed

### Logs

View package manager logs:
```bash
cat /var/log/kpm.log
```

### Getting Help

For additional help:
```bash
kpm --help
kpm <command> --help
```

## Best Practices

1. **Keep Your System Updated**
   ```bash
   kpm update
   kpm upgrade
   ```

2. **Clean Up**
   ```bash
   kpm autoremove
   kpm clean
   ```

3. **Check Dependencies**
   ```bash
   kpm depends <package>
   kpm rdepends <package>
   ```

4. **Backup Your System**
   - Back up `/etc/kpm/repos.d/` for repository configurations
   - Keep a list of installed packages: `kpm list --installed > packages.list`

## Next Steps

- [Basic Commands](./basic-commands.md) - Learn essential KOS commands
- [Developer Guide](../developer-guide/creating-packages.md) - Create your own packages
- [Advanced Topics](../advanced/README.md) - Advanced package management techniques

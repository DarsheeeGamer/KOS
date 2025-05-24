# KOS Package Management

This guide introduces KOS Package Manager (KPM), a powerful tool for managing packages, repositories, and applications within your KOS environment. KPM provides robust dependency resolution, advanced indexing, and comprehensive management capabilities for all your software needs.

## Overview

KPM provides a comprehensive suite of commands for:

- Installing, removing, and searching for packages
- Managing package repositories with advanced priority and dependency resolution
- Installing and managing applications with comprehensive metadata
- Updating package indexes with optimized search capabilities
- Integrating with pip for Python package management
- Monitoring system resource usage during package operations
- Advanced dependency resolution and conflict detection
- Repository management with versioning and priority control

## Basic Usage

All package management functionality is accessed through the `kpm` command:

```
kpm [command] [options]
```

## Package Management

### Installing Packages

Install a package from the configured repositories:

```
kpm install [package-name]
```

Options:
- `--force` - Force reinstallation of already installed packages

### Removing Packages

Remove an installed package:

```
kpm remove [package-name]
```

### Listing Installed Packages

View a list of all installed packages:

```
kpm list
```

### Searching for Packages

Search for packages by name, description, or tags:

```
kpm search [query]
```

### Updating Package Index

Update the package index from all active repositories:

```
kpm update
```

## Repository Management

KPM allows you to manage multiple package repositories to extend available packages.

### Adding a Repository

Add a new package repository:

```
kpm repo-add [name] [url]
```

Example:
```
kpm repo-add custom https://myrepo.com/kos
```

### Removing a Repository

Remove a configured repository:

```
kpm repo-remove [name]
```

### Listing Repositories

List all configured repositories:

```
kpm repo-list
```

### Updating Repository Index

Update the package index for a specific repository:

```
kpm repo-update [name]
```

Update all repositories:
```
kpm repo-update
```

## Application Management

KPM also manages applications, which are higher-level software packages with specialized functionality.

### Installing Applications

Install an application:

```
kpm app-install [app-name]
```

### Removing Applications

Remove an installed application:

```
kpm app-remove [app-name]
```

### Listing Installed Applications

View a list of all installed applications:

```
kpm app-list
```

### Searching for Applications

Search for applications by name, description, or category:

```
kpm app-search [query]
```

## Examples

Here are some common usage examples:

1. Install the numpy package:
   ```
   kpm install numpy
   ```

2. Search for text processing packages:
   ```
   kpm search text
   ```

3. Add a custom repository:
   ```
   kpm repo-add custom https://myrepo.com/kos
   ```

4. Update all package repositories:
   ```
   kpm update
   ```

5. List all installed applications:
   ```
   kpm app-list
   ```

## Advanced Features

### Advanced Dependency Resolution

KPM features robust dependency resolution that can handle complex dependency graphs:

```
kpm resolve [package-name]
```

This command analyzes dependencies, detects conflicts, and provides a detailed report of the dependency tree.

### Monitoring System

KPM includes comprehensive monitoring of package operations:

```
kpm stats [days]
```

View statistics about package operations, including success rates, durations, and resource usage for the specified number of days (default: 7).

### Enhanced PIP Integration

KPM provides advanced pip integration for Python package management:

```
kpm pip-install [package] [options]
kpm pip-remove [package] [options]
kpm pip-list [options]
kpm pip-search [query]
kpm pip-update [package]
kpm pip-freeze [output-file]
kpm pip-requirements [input-file]
```

Options include:
- `--upgrade`: Upgrade packages if already installed
- `--user`: Install to user site-packages
- `--no-deps`: Don't install dependencies
- `--index-url=URL`: Use alternative package index

### Repository Management

Advanced repository management with priority control:

```
kpm repo-add [name] [url] [options]
kpm repo-remove [name] [options]
kpm repo-list [options]
kpm repo-update [name] [options]
kpm repo-enable [name]
kpm repo-disable [name]
kpm repo-priority [name] [priority]
```

Options include:
- `--active=yes/no`: Set repository active status
- `--priority=N`: Set repository priority (lower is higher priority)
- `--no-update`: Don't update repository after adding
- `--force`: Force removal even if packages are installed
- `--verbose`: Show detailed information
- `--json`: Output in JSON format

### Application Management

Comprehensive application management:

```
kpm app-install [name] [options]
kpm app-remove [name] [options]
kpm app-list [options]
kpm app-search [query] [options]
kpm app-update [name] [options]
kpm app-info [name]
```

Options include:
- `--version=VERSION`: Install specific version
- `--force`: Force reinstall if already installed
- `--no-deps`: Do not install dependencies
- `--user`: Install in user directory
- `--purge`: Remove configuration files as well
- `--keep-deps`: Keep dependencies installed
- `--verbose`: Show detailed information
- `--upgradable`: Show only upgradable applications
- `--json`: Output in JSON format

### System Integration

KPM integrates with KADVLayer for advanced system monitoring and resource management:

```
kpm monitor [operation]
```

This provides real-time monitoring of system resources during package operations.

### Maintenance Commands

KPM includes maintenance commands for system health:

```
kpm clean [options]   # Clean package cache and temporary files
kpm repair [options]  # Repair package database
```

Options include:
- `--force`: Force cleanup/repair operations
- `--dry-run`: Show what would be done without making changes
- `--verbose`: Show detailed information

## Repository Priority

When multiple repositories contain the same package, KPM uses the following priority order:
1. User-specified repository (if provided)
2. Repository priority setting (lower number = higher priority)
3. Repositories in order of addition (first added has higher priority)

## Application Categories

Applications are organized by categories to make them easier to discover. Common categories include:
- Development
- Utilities
- Science
- Media
- Games
- Education

### Package Versions

KPM supports versioned packages. By default, it installs the latest available version, but you can specify a particular version with:

```
kpm install package-name=1.2.3
```

## Troubleshooting

If you encounter issues with KPM, try these troubleshooting steps:

1. Update your package index:
   ```
   kpm update
   ```

2. Check repository status:
   ```
   kpm repo-list
   ```

3. Ensure the repository containing your desired package is active.

4. For connection issues, verify your network connection and that repository URLs are correct.

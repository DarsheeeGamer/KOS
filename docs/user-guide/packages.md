# Package Management

This guide covers package management in KOS, including installing, updating, and removing software packages.

## Package Management Overview

KOS uses a package manager to handle software installation, updates, and removal. The package manager helps maintain system stability by managing dependencies and ensuring proper installation.

## Basic Commands

### Update Package Lists

Update the list of available packages:

```bash
update
```

### Install a Package

Install a new package:

```bash
install package_name
```

### Remove a Package

Remove an installed package:

```bash
uninstall package_name
```

### Search for Packages

Search for available packages:

```bash
search search_term
```

### List Installed Packages

List all installed packages:

```bash
list
```

## Advanced Package Management

### Install Specific Version

Install a specific version of a package:

```bash
install package_name=version
```

### Hold Package Version

Prevent a package from being upgraded:

```bash
hold package_name
```

### Unhold Package

Allow a package to be upgraded:

```bash
unhold package_name
```

### View Package Information

Show detailed information about a package:

```bash
info package_name
```

### List Package Files

List files installed by a package:

```bash
list-files package_name
```

## Repository Management

### List Configured Repositories

```bash
repo list
```

### Add a Repository

```bash
repo add repository_url
```

### Remove a Repository

```bash
repo remove repository_name
```

### Update Repository Information

```bash
repo update
```

## Dependency Management

### Check for Broken Dependencies

```bash
check
```

### Fix Broken Dependencies

```bash
fix-dependencies
```

### Show Dependencies

Show dependencies for a package:

```bash
depends package_name
```

## System Upgrade

### Upgrade All Packages

Upgrade all installed packages to their latest versions:

```bash
upgrade
```

### Distribution Upgrade

Upgrade the entire distribution to a new release:

```bash
dist-upgrade
```

## Package Verification

### Verify Package Integrity

Check the integrity of installed packages:

```bash
verify
```

### Check for Security Updates

List available security updates:

```bash
security-updates
```

## Package Sources

### Install from Source

Install a package from source:


```bash
install-source package_url
```

### Build Package from Source

Build a package from source:

```bash
build-package source_directory
```

## Package Management Best Practices

1. Always keep your system up to date
2. Only install packages from trusted sources
3. Regularly clean up unused packages
4. Review package permissions and configurations
5. Keep backups of important configuration files
6. Read package changelogs before upgrading
7. Use version control for configuration files

## Troubleshooting

### Fix Broken Package Database

```bash
fix-database
```

### Clean Package Cache

```bash
clean
```

### Reinstall a Package

```bash
reinstall package_name
```

### View Package Logs

```bash
view-logs package_name
```

## Package Management Security

### Verify Package Signatures

```bash
verify-signature package_file
```

### Add Repository Key

```bash
add-key key_file
```

### Remove Repository Key

```bash
remove-key key_id
```

## Custom Packages

### Create Package from Directory

```bash
create-package directory_path
```

### Build Package from Spec

```bash
build-spec spec_file
```

### Lint Package

Check package for common issues:

```bash
lint-package package_file
```

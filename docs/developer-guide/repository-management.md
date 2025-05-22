# Repository Management in KOS

This guide covers the management of KOS package repositories, including creation, configuration, and maintenance.

## Table of Contents
- [Repository Structure](#repository-structure)
- [Creating a Repository](#creating-a-repository)
- [Package Index](#package-index)
- [Repository Configuration](#repository-configuration)
- [Repository Management](#repository-management)
- [Repository Security](#repository-security)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Repository Structure

A KOS package repository follows this structure:

```
repository/
├── dists/
│   └── stable/
│       ├── main/
│       │   └── binary-all/
│       │       └── Packages.gz
│       └── Release
├── pool/
│   └── main/
│       └── p/
│           └── package-name/
│               ├── package-name_1.0.0-1_all.kos
│               └── package-name_1.0.0-1_all.kos.sig
└── kos-archive-keyring.gpg
```

## Creating a Repository

### Initialize Repository
```bash
# Create repository directory structure
$ mkdir -p repo/dists/stable/main/binary-all
$ mkdir -p repo/pool/main

# Create configuration file
$ cat > repo/kos-repo.conf <<EOF
[Repository]
Name=My Repository
Description=My custom KOS repository
Version=1.0
Architectures=all
Components=main
SignWith=default
EOF
```

### Add Packages
```bash
# Copy package files to pool
$ cp package_1.0.0-1_all.kos repo/pool/main/p/package-name/

# Generate package index
$ kos-repo update
```

## Package Index

The package index (`Packages.gz`) contains metadata for all packages in the repository.

### Manual Index Creation
```bash
# Create Packages file
$ cd repo
$ dpkg-scanpackages --multiversion pool/ > dists/stable/main/binary-all/Packages

# Create compressed index
$ gzip -k -f dists/stable/main/binary-all/Packages

# Create Release file
$ apt-ftparchive release -c kos-repo.conf dists/stable/ > dists/stable/Release
```

### Automatic Indexing
```bash
# Install kos-repo-tools
$ sudo apt install kos-repo-tools

# Configure automatic indexing
$ sudo nano /etc/kos/repo/config.toml

[repository]
path = "/path/to/repo"
components = ["main"]
architectures = ["all"]

# Enable and start the service
$ sudo systemctl enable --now kos-repo-indexer
```

## Repository Configuration

### Repository Configuration File
```ini
[Repository]
# Required
Name=My Repository
Description=My custom KOS repository
Version=1.0

# Optional
Components=main,contrib,non-free
Architectures=all,amd64,arm64
SignWith=default
UpdateFrequency=hourly
MaxPackages=1000
MaxPackageSize=100MB

[Component:main]
Description=Main component
Priority=required

[Component:contrib]
Description=Contributed packages
Priority=optional

[Component:non-free]
Description=Non-free packages
Priority=optional
```

### Repository Signing
```bash
# Generate GPG key
$ gpg --full-generate-key

# Export public key
$ gpg --export -a "My Repository" > repo/kos-archive-keyring.gpg

# Sign repository
$ kos-repo sign --key-id your-key-id
```

## Repository Management

### Adding a Repository
```bash
# Add repository
$ kos-repo add myrepo https://example.com/kos/repo stable main

# Add repository from file
$ kos-repo add-from-file /path/to/repo.list

# List repositories
$ kos-repo list
```

### Updating Repositories
```bash
# Update package lists
$ kos-repo update

# Update a specific repository
$ kos-repo update myrepo
```

### Removing a Repository
```bash
# Remove repository
$ kos-repo remove myrepo

# Remove all repositories
$ kos-repo remove --all
```

## Repository Security

### GPG Key Management
```bash
# Import repository key
$ sudo apt-key add kos-archive-keyring.gpg

# List trusted keys
$ apt-key list

# Remove key
$ sudo apt-key del key-id
```

### Repository Verification
```bash
# Verify repository signature
$ kos-repo verify

# Check package signatures
$ kos-pkg verify package.kos
```

## Best Practices

### Repository Maintenance
1. Keep repository size manageable
2. Regularly clean up old package versions
3. Sign all packages and the repository
4. Maintain a changelog
5. Backup the repository regularly

### Package Management
1. Use semantic versioning
2. Include proper dependencies
3. Provide comprehensive package metadata
4. Test packages before publishing
5. Document package installation and removal

## Troubleshooting

### Common Issues

1. **Repository Not Found**
   ```bash
   # Check repository URL
   $ kos-repo list
   
   # Check network connectivity
   $ ping example.com
   $ curl -I https://example.com/kos/repo/dists/stable/Release
   ```

2. **Signature Verification Failed**
   ```bash
   # Import repository key
   $ wget -qO- https://example.com/kos/repo/kos-archive-keyring.gpg | sudo apt-key add -
   
   # Update package lists
   $ kos-repo update
   ```

3. **Package Installation Failed**
   ```bash
   # Check dependencies
   $ kos-pkg depends package.kos
   
   # Install with --force
   $ sudo kos-pkg install --force package.kos
   ```

## Advanced Topics

### Repository Mirroring
```bash
# Create mirror configuration
$ cat > /etc/kos/mirror.conf <<EOF
[mirror]
base_url = "http://archive.kos.org/kos/"
architectures = ["all", "amd64"]
components = ["main"]
method = "rsync"
interval = 6

[filter]
include = ["*_all.kos", "*_amd64.kos"]
```

### Repository Proxying
```bash
# Configure nginx as a repository proxy
server {
    listen 80;
    server_name repo.example.com;

    location /kos/ {
        proxy_pass http://localhost:8080/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Repository Statistics
```bash
# Install reporting tools
$ sudo apt install kos-repo-stats

# Generate statistics
$ kos-repo-stats --output=html > stats.html
```

## See Also
- [Creating Packages](./creating-packages.md)
- [Package Metadata](./package-metadata.md)
- [Developer Guide](../developer-guide/README.md)

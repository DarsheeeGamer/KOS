# Build Scripts

This directory contains utility scripts for building and managing the KOS documentation.

## Available Scripts

### `build-docs.ps1`

Builds and serves the KOS documentation locally using MkDocs.

**Usage:**

```powershell
# Install dependencies and serve documentation (default)
.\scripts\build-docs.ps1

# Only install dependencies (no build or serve)
.\scripts\build-docs.ps1 -InstallDeps

# Only build documentation (no serve)
.\scripts\build-docs.ps1 -BuildOnly
```

**Requirements:**
- Windows PowerShell 5.1 or later
- Python 3.8 or later
- Git (for version control features)

## Development

### Adding New Scripts

1. Create a new `.ps1` file in this directory
2. Add a section to this README explaining the script's purpose and usage
3. Include proper error handling and documentation
4. Test the script on a clean environment

### Best Practices

- Use PowerShell Core (pwsh) for cross-platform compatibility
- Include error handling and input validation
- Document all parameters and usage examples
- Follow PowerShell coding conventions
- Test scripts in a clean environment

## License

These scripts are licensed under the same terms as the KOS project (MIT).

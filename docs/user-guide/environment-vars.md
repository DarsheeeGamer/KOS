# Environment Variables in KOS

This guide covers environment variables, their usage, and management in KOS.

## Table of Contents
- [Introduction](#introduction)
- [Viewing Environment Variables](#viewing-environment-variables)
- [Setting Environment Variables](#setting-environment-variables)
- [Common Environment Variables](#common-environment-variables)
- [Shell Configuration Files](#shell-configuration-files)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [Advanced Topics](#advanced-topics)

## Introduction

Environment variables are named values that affect the way running processes behave. They are part of the environment in which a process runs and are commonly used to configure applications and shell behavior.

## Viewing Environment Variables

### List All Variables
```bash
# Print all environment variables
$ printenv
$ env

# Print a specific variable
$ echo $HOME
$ echo $PATH

# Search for variables
$ env | grep -i path
```

### Show Variable Attributes
```bash
# Show variable attributes (in bash)
$ declare -p VARIABLE

# Check if variable is set
$ [ -z "$VARIABLE" ] && echo "Not set" || echo "Value: $VARIABLE"
```

## Setting Environment Variables

### Temporary Variables
```bash
# Set for current session
$ MY_VAR="value"

# Set for single command
$ MY_VAR="value" command

# Append to PATH
$ export PATH="$PATH:/new/path"
```

### Persistent Variables
```bash
# Add to ~/.bashrc or ~/.bash_profile
export MY_VAR="value"

# Source the file to apply changes
$ source ~/.bashrc
```

### System-wide Variables
```bash
# Add to /etc/environment (no export needed)
MY_VAR="value"

# Or create a file in /etc/profile.d/
$ sudo nano /etc/profile.d/myapp.sh
export MY_VAR="value"
```

## Common Environment Variables

### System Variables
- `HOME`: User's home directory
- `PATH`: Command search path
- `USER`: Current username
- `SHELL`: Current shell
- `PWD`: Current working directory
- `OLDPWD`: Previous working directory
- `HOSTNAME`: System hostname
- `LANG`, `LC_*`: Locale settings
- `TERM`: Terminal type
- `EDITOR`: Default text editor
- `VISUAL`: Preferred visual editor

### Application Variables
- `HTTP_PROXY`, `HTTPS_PROXY`: Proxy settings
- `JAVA_HOME`: Java installation directory
- `PYTHONPATH`: Python module search path
- `GOPATH`: Go workspace directory
- `NODE_PATH`: Node.js module search path
- `DOCKER_*`: Docker configuration

## Shell Configuration Files

### Bash Configuration
- `~/.bashrc`: Executed for interactive non-login shells
- `~/.bash_profile`: Executed for login shells
- `~/.bash_logout`: Executed on shell exit
- `~/.profile`: Fallback for `~/.bash_profile`
- `/etc/profile`: System-wide initialization file
- `/etc/bash.bashrc`: System-wide .bashrc

### Loading Order
1. `/etc/profile`
2. `~/.bash_profile`
3. `~/.bashrc`
4. `~/.bash_login`
5. `~/.profile`

## Best Practices

### Variable Naming
- Use UPPERCASE for environment variables
- Use underscores to separate words
- Be descriptive but concise
- Avoid special characters

### Security
- Don't store sensitive data in environment variables
- Use appropriate file permissions for config files
- Consider using .env files for development
- Use `export -n` to unset exported variables

### Portability
- Use `${VAR:-default}` for default values
- Quote variable expansions: `"$VAR"`
- Use absolute paths in scripts
- Document required environment variables

## Troubleshooting

### Common Issues

1. **Variable Not Set**
   ```bash
   # Check if variable is exported
   $ printenv VARIABLE
   
   # Check shell configuration files
   $ grep -r VARIABLE ~/.* /etc/profile.d/
   ```

2. **Incorrect Value**
   ```bash
   # Check for overrides
   $ env | grep -i variable
   
   # Check all configuration files
   $ cat ~/.bashrc ~/.profile /etc/environment 2>/dev/null | grep -i variable
   ```

3. **Command Not Found**
   ```bash
   # Check PATH
   $ echo $PATH
   
   # Check command location
   $ which command
   $ type -a command
   ```

## Advanced Topics

### Process Substitution
```bash
# Set variable for command substitution
$ files=$(ls)
$ count=$(wc -l < file.txt)
```

### Variable Expansion
```bash
# Default value
${VAR:-default}

# Error if unset
${VAR:?Error message}

# Replace if set
${VAR:+replacement}

# Substring
${VAR:offset:length}

# Pattern matching
${VAR#pattern}  # Remove shortest prefix
${VAR##pattern} # Remove longest prefix
${VAR%pattern}  # Remove shortest suffix
${VAR%%pattern} # Remove longest suffix
```

### Environment Variable Files
```bash
# Load .env file
export $(grep -v '^#' .env | xargs)

# Or use direnv
# .envrc
export VAR=value
```

### Shell Options
```bash
# Exit on undefined variable
set -u

# Debug mode
set -x

# Disable globbing
set -f
```

## See Also
- [Shell Scripting Guide](./shell-scripting.md)
- [Process Management](./process-management.md)
- [User Management](./user-management.md)

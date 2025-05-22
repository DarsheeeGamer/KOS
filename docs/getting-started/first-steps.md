# First Steps with KOS

Welcome to KOS! This guide will help you take your first steps with the Kaede Operating System.

## Starting KOS

1. Open a terminal
2. Navigate to your KOS directory
3. Run: `python main.py`

You should see the KOS prompt:
```
kaede@kos:/$ 
```

## Basic Navigation

### List Directory Contents
```bash
ls
```

### Change Directory
```bash
cd directory_name
cd ..          # Go up one directory
cd /           # Go to root directory
cd ~           # Go to home directory
```

### View Current Directory
```bash
pwd
```

## Managing Packages

### List Available Packages
```bash
kpm list
```

### Install a Package
```bash
kpm install package_name
```

### Remove a Package
```bash
kpm remove package_name
```

## Getting Help

### List Available Commands
```bash
help
```

### Get Help on a Specific Command
```bash
help command_name
```

## Basic File Operations

### View File Contents
```bash
cat filename
```

### Create a Directory
```bash
mkdir directory_name
```

### Create a File
```bash
touch filename
```

### Copy Files
```bash
cp source destination
```

### Move/Rename Files
```bash
mv source destination
```

### Remove Files
```bash
rm filename
rm -r directory_name  # Remove directory recursively
```

## User Management

### View Current User
```bash
whoami
```

### Switch User
```bash
su username
```

## Exiting KOS

To exit KOS, type:
```bash
exit
```

## Next Steps

Now that you've learned the basics, you might want to:

1. Explore the [User Guide](../user-guide/README.md) for more detailed information
2. Learn about [package management](../user-guide/package-management.md)
3. Check out [advanced features](../advanced/README.md)

Remember, you can always type `help` in the KOS shell to see available commands and get help.

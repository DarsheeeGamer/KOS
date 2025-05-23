# First Steps with KOS

Welcome to KOS! This guide will help you get started with the basic usage of the KOS shell.

## Starting KOS

To start the KOS shell, simply run:

```bash
kos
```

You should see a prompt similar to:

```
kos > 
```

## Basic Navigation

### Listing Files

Use the `ls` command to list files in the current directory:

```bash
ls
```

### Changing Directories

Navigate to a different directory with `cd`:

```bash
cd /path/to/directory
```

### Viewing Current Directory

To see your current working directory:

```bash
pwd
```

## Working with Files

### Creating Files

Create a new file with `touch`:

```bash
touch newfile.txt
```

### Viewing File Contents

View the contents of a file with `cat`:

```bash
cat filename.txt
```

### Creating Directories

Create a new directory with `mkdir`:

```bash
mkdir new_directory
```

## Getting Help

To see a list of available commands:

```bash
help
```

For help with a specific command:

```bash
help command_name
```

## Exiting KOS

To exit the KOS shell:

```bash
exit
```

## Next Steps

Now that you're familiar with the basics, you can explore more advanced features:

- [Command Reference](../user-guide/commands.md)
- [File System Guide](../user-guide/filesystem.md)
- [Process Management](../user-guide/processes.md)

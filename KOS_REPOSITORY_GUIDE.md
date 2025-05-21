# KOS Repository Creation Guide

This guide provides detailed instructions for creating and managing repositories for the Kaede Operating System (KOS) using the `repo_creator.py` tool.

## Table of Contents

- [Repository Structure](#repository-structure)
- [Using repo_creator.py](#using-repo_creatorpy)
- [Package Manifest Requirements](#package-manifest-requirements)
- [Advanced Repository Management](#advanced-repository-management)

---

## Repository Structure

A KPM (Kaede Package Manager) repository has the following structure:

```
repository/
├── files/           # Contains packages organized by name
│   ├── app1/        # Each app in its own directory
│   │   ├── package.json
│   │   ├── main.py
│   │   └── ...
│   └── app2/
│       ├── package.json
│       └── ...
└── index.json       # Repository index listing all packages
```

The `index.json` file contains metadata about all packages in the repository, which helps the package manager locate and install applications.

## Using repo_creator.py

The `repo_creator.py` script simplifies the process of creating and maintaining package repositories.

### Setup a New Repository

1. Execute the script without arguments to create the basic structure:

```bash
python repo_creator.py
```

This will:
- Create a `files` directory for your packages
- Create a `repo` directory for the repository
- Initialize an empty repository index (`repo/index.json`)

### Adding Packages to the Repository

1. Create a directory for your package inside the `files` directory:
   ```
   files/my_package/
   ```

2. Add all your package files, ensuring you include a valid `package.json` manifest:
   ```
   files/my_package/
   ├── package.json
   ├── main.py
   └── ... (other files)
   ```

3. Run the repo creator script again to process the packages:
   ```bash
   python repo_creator.py
   ```

The script will:
- Process each package directory
- Calculate checksums and file sizes
- Copy packages to the repository
- Update the repository index

## Package Manifest Requirements

Each package must include a `package.json` file with the following required fields:

```json
{
  "name": "app_name",
  "version": "1.0.0",
  "description": "A description of the application",
  "author": "Your Name",
  "main": "main.py"
}
```

### Required Fields

| Field | Description |
|-------|-------------|
| name | Package name (must be unique in the repository) |
| version | Package version (semantic versioning recommended) |
| description | Short description of the package |
| author | Name of the package creator |
| main | Main entry point file |

### Optional Fields

You can enhance your package manifest with these optional fields:

```json
{
  "dependencies": ["package1", "package2"],
  "homepage": "https://example.com/my-app",
  "license": "MIT",
  "tags": ["utility", "system"],
  "cli_aliases": ["cmd1", "cmd2"],
  "cli_function": "main_cli_function"
}
```

## Advanced Repository Management

### Updating Packages

To update an existing package:

1. Modify the files in the `files/package_name` directory
2. Update the version number in the `package.json` file
3. Run `repo_creator.py` again to update the repository

### Validating the Repository

After creating or updating your repository, you can validate it by:

1. Checking that all packages have valid package.json files
2. Ensuring all required files referenced in package.json exist
3. Verifying the repository index contains all expected packages

### Repository Distribution

To distribute your repository:

1. Host the entire `repo` directory on a web server
2. Share the repository URL with users
3. Users can then add your repository to their KPM configuration and install packages from it

Remember to increment version numbers when updating packages to ensure users receive the updated versions.

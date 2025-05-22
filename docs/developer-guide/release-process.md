# KOS Release Process

This document outlines the process for creating a new release of KOS.

## Table of Contents
- [Release Schedule](#release-schedule)
- [Pre-Release Checklist](#pre-release-checklist)
- [Versioning](#versioning)
- [Creating a Release](#creating-a-release)
- [Release Notes](#release-notes)
- [Post-Release Tasks](#post-release-tasks)
- [Hotfix Releases](#hotfix-releases)
- [Rolling Back a Release](#rolling-back-a-release)

## Release Schedule

KOS follows a time-based release schedule:

- **Major Releases (X.0.0)**: Every 6 months
- **Minor Releases (X.Y.0)**: Every 2 months
- **Patch Releases (X.Y.Z)**: As needed for critical bug fixes

## Pre-Release Checklist

Before creating a release, ensure the following:

1. **Code Freeze**
   - All features for the release are merged
   - No new features should be merged after code freeze

2. **Testing**
   - All tests are passing
   - No critical bugs are open for the release
   - Performance testing completed
   - Security audit completed

3. **Documentation**
   - All new features are documented
   - API documentation is up to date
   - Changelog is updated
   - Upgrade guide is prepared

4. **Dependencies**
   - All dependencies are up to date
   - No known security vulnerabilities
   - License compatibility verified

## Versioning

KOS follows [Semantic Versioning](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for backward-compatible functionality
- **PATCH** version for backward-compatible bug fixes

## Creating a Release

### 1. Prepare the Release Branch

```bash
# Ensure main is up to date
git checkout main
git pull origin main

# Create a release branch
git checkout -b release/vX.Y.Z
```

### 2. Update Version Information

```bash
# Update __version__ in kos/__init__.py
echo "__version__ = 'X.Y.Z'" > kos/__version__.py

# Update version in setup.py
# Update version in docs/conf.py
```

### 3. Update Changelog

```bash
# Generate changelog
git log --pretty=format:"- %s" vX.Y.Z..HEAD > CHANGELOG.md

# Edit CHANGELOG.md to organize changes:
# - Added: New features
# - Changed: Changes in existing functionality
# - Deprecated: Soon-to-be removed features
# - Removed: Removed features
# - Fixed: Bug fixes
# - Security: Vulnerability fixes
```

### 4. Commit Changes

```bash
git add .
git commit -m "Prepare for vX.Y.Z release"
```

### 5. Create a Release PR

```bash
git push origin release/vX.Y.Z
# Create a PR from release/vX.Y.Z to main
```

### 6. Tag the Release

After the PR is merged:

```bash
# Pull the latest changes
git checkout main
git pull origin main

# Create and push the tag
git tag -a vX.Y.Z -m "Version X.Y.Z"
git push origin vX.Y.Z
```

### 7. Build and Publish

```bash
# Build the package
python setup.py sdist bdist_wheel

# Test the package
twine upload --repository testpypi dist/*

# Publish to PyPI
twine upload dist/*
```

### 8. Create GitHub Release

1. Go to [Releases](https://github.com/DarsheeeGamer/KOS/releases)
2. Click "Draft a new release"
3. Enter the tag version (vX.Y.Z)
4. Set release title to "KOS X.Y.Z"
5. Paste the changelog in the description
6. Attach the built packages
7. Publish the release

## Release Notes

Release notes should include:

1. **Overview**: Brief description of the release
2. **What's New**: Major features and improvements
3. **Upgrade Notes**: Important changes from previous versions
4. **Breaking Changes**: If any, with migration instructions
5. **Deprecations**: Features that will be removed in future versions
6. **Bug Fixes**: List of fixed issues
7. **Contributors**: Thank contributors

## Post-Release Tasks

1. **Update Documentation**
   - Update the documentation site
   - Update any version-specific documentation

2. **Announce the Release**
   - Post on the project blog
   - Announce on mailing lists
   - Share on social media

3. **Prepare for Next Release**
   - Update version to next development version (e.g., X.Y.Z+1.dev0)
   - Create a new milestone for the next release
   - Update the roadmap

## Hotfix Releases

For critical bug fixes:

1. Create a branch from the latest release tag
2. Apply the fix
3. Bump the patch version
4. Follow the release process

## Rolling Back a Release

If a critical issue is found after release:

1. **Immediate Action**
   - Mark the release as deprecated on PyPI
   - Add a warning to the GitHub release
   - Communicate the issue to users

2. **Create a Fix**
   - Follow the hotfix process
   - Release a new version as soon as possible

## Release Automation

### GitHub Actions Workflow

```yaml
name: Release

on:
  push:
    tags:
      - 'v*.*.*'

jobs:
  build-and-publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
          
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install setuptools wheel twine
          
      - name: Build package
        run: |
          python setup.py sdist bdist_wheel
          
      - name: Publish to PyPI
        env:
          TWINE_USERNAME: ${{ secrets.PYPI_USERNAME }}
          TWINE_PASSWORD: ${{ secrets.PYPI_PASSWORD }}
        run: |
          twine upload dist/*
```

## Release Calendar

| Version | Code Freeze | Release Date | Status       |
|---------|-------------|--------------|--------------|
| 1.0.0   | 2023-06-01  | 2023-06-15   | Released     |
| 1.1.0   | 2023-08-01  | 2023-08-15   | In Progress  |
| 2.0.0   | 2023-12-01  | 2023-12-15   | Planned      |

## See Also
- [Contributing Guide](./contributing.md)
- [Versioning Policy](./versioning-policy.md)
- [Maintainer Guide](./maintainer-guide.md)

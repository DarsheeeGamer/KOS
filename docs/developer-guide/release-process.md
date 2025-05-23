# Release Process

This document outlines the process for creating a new release of KOS.

## Release Schedule

KOS follows [Semantic Versioning](https://semver.org/). The release schedule is as follows:

- **Major releases (X.0.0)**: As needed for breaking changes
- **Minor releases (X.Y.0)**: Monthly, on the first Monday of the month
- **Patch releases (X.Y.Z)**: As needed for critical bug fixes

## Pre-Release Checklist

Before creating a release, ensure the following:

- [ ] All tests are passing
- [ ] Documentation is up to date
- [ ] Changelog is updated
- [ ] Dependencies are up to date
- [ ] No known critical bugs

## Version Bumping

Update the version number in these files:

1. `kos/__init__.py`
2. `setup.py`
3. `CHANGELOG.md`

## Creating a Release

### 1. Create Release Branch

```bash
git checkout -b release/vX.Y.Z
```

### 2. Update Changelog

Update `CHANGELOG.md` with the following sections:

- Added
- Changed
- Deprecated
- Removed
- Fixed
- Security

### 3. Commit Changes

```bash
git add .
git commit -m "chore: prepare for vX.Y.Z release"
```

### 4. Tag the Release

```bash
git tag -a vX.Y.Z -m "Version X.Y.Z"
```

### 5. Push Changes

```bash
git push origin release/vX.Y.Z
git push --tags
```

### 6. Create GitHub Release

1. Go to [Releases](https://github.com/yourusername/kos/releases)
2. Click "Draft a new release"
3. Enter the tag version (vX.Y.Z)
4. Set release title to "Version X.Y.Z"
5. Copy the changelog entries into the release notes
6. Publish the release

### 7. Publish to PyPI

Build and upload the package to PyPI:

```bash
python setup.py sdist bdist_wheel
twine upload dist/*
```

## Post-Release Tasks

1. Merge the release branch into main and develop
2. Update the development version in `kos/__init__.py`
3. Announce the release on:
   - GitHub Discussions
   - Discord/Slack
   - Twitter

## Hotfix Releases

For critical bug fixes:

1. Create a hotfix branch from the latest release tag
2. Apply the fix
3. Bump the patch version
4. Follow the regular release process

## Rolling Back a Release

If a release has critical issues:

1. Create a new release that reverts the problematic changes
2. Mark the problematic release as deprecated on GitHub
3. Update the documentation to warn users about the problematic version

## Release Notes Guidelines

- Be clear and concise
- Group changes by category
- Include issue/PR numbers
- Highlight breaking changes
- Provide upgrade instructions if needed

## Release Dependencies

- Python 3.8+
- setuptools
- wheel
- twine
- GitHub CLI (optional)

## Troubleshooting

### Failed Build

If the build fails:
1. Check the error message
2. Fix the issue
3. Bump the version
4. Retry the release

### Failed Upload

If the upload to PyPI fails:
1. Check your credentials
2. Ensure the version doesn't already exist
3. Try with `--skip-existing` if needed

## Security Releases

For security-related releases:
1. Create a private security advisory on GitHub
2. Prepare the fix in a private branch
3. Coordinate with the security team
4. Follow the regular release process once ready

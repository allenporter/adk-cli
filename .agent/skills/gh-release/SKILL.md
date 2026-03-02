---
name: gh-release
description: Automates version bumping in pyproject.toml and creating GitHub releases. Use when releasing a new version of a project.
---

# GitHub Release Skill

## Overview

This skill automates the process of creating a new release. It updates the `version` in `pyproject.toml`, commits the change, and then creates a GitHub release using the `gh` CLI tool.

## Semantic Versioning (SemVer)

This project follows [Semantic Versioning](https://semver.org/) (SemVer) for releasing versions. SemVer uses a `MAJOR.MINOR.PATCH` format:

- **MAJOR** version when you make incompatible API changes.
- **MINOR** version when you add functionality in a backward compatible manner.
- **PATCH** version when you make backward compatible bug fixes.

Example: `1.0.0` -> `1.1.0` (new feature), `1.1.0` -> `1.1.1` (bug fix), `1.1.1` -> `2.0.0` (breaking change).

## Usage

To use this skill, execute the `create-release.sh` script from the root of your project with the desired new version number as an argument.

**Example:**

```bash
./.agent/skills/gh-release/scripts/create-release.sh 0.1.0
```

This will perform the following actions:

1. Find the `pyproject.toml` file in the project root.
2. Update the `version` field in `pyproject.toml` to the specified version.
3. Stage the `pyproject.toml` file.
4. Commit the change with the message `chore(release): <version>`.
5. Create a GitHub release with auto-generated release notes using `gh release create`.

## Requirements

- `gh` CLI tool must be installed and authenticated.
- The script should be run from the root of the project repository.
- `python` must be available (used for safe TOML editing).

## Resources

### scripts/

- `create-release.sh`: The main script that performs the release automation.

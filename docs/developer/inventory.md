# Using the Inventory Asset Management Tool

## Table of Contents

- [Overview](#overview)
- [Config Spec](#config-spec)
  - [General Structure](#general-structure)
  - [Fields Description](#fields-description)
- [Running the Script](#running-the-script)
    - [lock](#lock)
    - [sync](#sync)
    - [list](#list)
  - [Common Arguments](#common-arguments)

---

## Overview

The `dev_scripts/inventory.py` tool is a Python script designed to manage assets
from GitHub releases. It expects a configuration file (in TOML format) that
contains a list of assets and some parameters. Using this config file, it can
query GitHub for release information, compute checksums for assets, update a
lock file (JSON format) and sync assets as described in the lock file.

If you come from a Python background, think of it like "Poetry, but for GitHub
assets".

## Config Spec

Before you begin working with the script, you must create a configuration file
in one of the following locations of your project:
* `inventory.toml`: This is a config file written specifically for this tool.
* `pyproject.toml`: This is a config file written for a Python project. The
  inventory tool expects a `[tool.inventory]` section in this file.

### General Structure

Each asset is defined as an entry under the `[asset]` section. For example:

```toml
[asset.example]
repo = "owner/repo"
version = ">=1.0.1"
platform."darwin/arm64"  = "asset-macos"
platform."linux/amd64"   = "asset-linux"
platform.all             = "asset-universal"
executable = true
destination = "./downloads/asset"
extract = false
```

If you are using `pyproject.toml` as a config file, then you need to prepend
`tool.inventory` to the section name, e.g., `[tool.inventory.asset.example]`.

### Fields Description

The table below lists the configuration fields supported for each asset entry
along with their possible values.

| Field         | Required | Description                                                                                                                                                      | Possible Values                                                                                                                                                                                                         |
|---------------|----------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `repo`                | yes | The GitHub repository identifier in the format `"owner/repo"`.                                                                                                   | Any valid GitHub repository string (e.g., `"octocat/Hello-World"`).                                                                                                        |
| `version`             | yes | A semantic versioning (semver) expression specifying the release version constraint for the asset. | Any valid semver expression, such as `">=1.0.1"`, `"==2.0.0"` ([options](https://python-semver.readthedocs.io/en/latest/usage/compare-versions-through-expression.html)).                                                                                                     |
| `platform.<platform>` | yes | Define the asset filename for specific platforms. Assets may have different filenames per platform. A fallback `platform.all` key can be used for platform-agnostic assets. | Keys like `platform."windows/amd64"`, `platform."linux/amd64"`, `platform."darwin/arm64"`; **Fallback Key:** `platform.all`. The value is the filename as a string. Templates with `{version}` are allowed. Use `"!tarball"` or `"!zipball"` to get the GitHub-generated source archives. |
| `executable`          | no  | Indicates whether the downloaded asset should be marked as executable.                                                                                           | `true` or `false` (default).                                                                                                                                                                                                     |
| `destination`         | yes | The local path where the asset should be saved after download. If the asset is a file, the destination will be its filename. Else, it will be the directory where the contents will be extracted in | Any valid file path string (e.g., `"downloads/asset.exe"`).                                                                                                                                                           |
| `extract`             | no  | Instructions for file extraction from the downloaded asset.                                                                                                    | `false` (default) for no extraction; a list of glob strings to extract matching files; or a table with keys (see below). |
| `extract.globs`       | no  | a list of glob strings to match specific files from an archive | Any valid glob such as `*.exe`, `bin/**/asset` ([options](https://docs.python.org/3/library/fnmatch.html)). Will extract all files in the archive if omitted.  |
| `extract.flatten`     | no  | copy the files to the destination root | `true` or `false` (default) |

## Running the Script

The inventory script supports three commands:
- `lock`
- `sync`
- `list`

#### lock

The `lock` command updates the lock file based on the configuration defined in
`pyproject.toml` / `inventory.toml`. For each asset, it reads its details,
queries GitHub to find the appropriate release and asset URL, computes a
checksum if the asset is available locally, uses caching for fetching and
hashing, renders filenames that contain the `{version}` template string, and
supports assets that are platform-agnostic using `platform.all`.

Example:

```
./dev_scripts/inventory.py lock
Processing 'asset1'
Processing 'asset2'
Lock file 'inventory.lock' updated.
```

#### sync

The `sync` command synchronizes (downloads or copies) assets as specified in the
lock file for the given platform (or the current platform if none is provided).
It downloads assets into a cache, verifies them against an expected hash, copies
them to the destination, marks files as executable if required, and extracts
files based on the provided extraction criteria.

Examples:

Sync all assets for the current platform:

```
./dev_scripts/inventory.py sync
Syncing 'asset1'
Syncing 'asset2'
Synced 2 assets.
```

Sync all assets for the provided platform:

```
./dev_scripts/inventory.py sync -p darwin/amd64
Syncing 'asset3'
Synced 1 assets.
```

Sync only specific assets:

```
./dev_scripts/inventory.py sync asset1
Syncing 'asset1'
Synced 1 assets.
```

#### list

The `list` command lists all assets defined for a specific platform, or the
current one, if not specified. The list output contains the name of the asset,
its version, and its download URL.

Example:

```
./dev_scripts/inventory.py list
asset1 0.0.1 https://github.com/owner/repo/releases/download/v0.0.1/asset1
asset2 1.2.3 https://github.com/owner/other/releases/download/v0.0.1/asset2
```

Pass `-vv` to get full details for each asset entry.

### Common Arguments

Each command supports the following optional arguments:

- `-p, --platform`:
  Specify the platform for which the assets should be processed. Examples
  include: `windows/amd64`, `linux/amd64`, `darwin/amd64`, `darwin/arm64`.
  If not provided, the current platform is auto-detected.

- `-v, --verbose`:
  Enable verbose logging. Use `-v` for INFO level or `-vv` (or more) for DEBUG
  level messaging.

- `-C, --directory`:
  Specify the working directory for the script. Defaults to the current working
  directory if not provided.

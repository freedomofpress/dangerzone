# Using the Inventory Asset Management Tool

## Table of Contents

- [Overview](#overview)
- [Configuration](#configuration)
  - [Examples](#examples)
  - [`repo`](#repo)
  - [`version`](#version)
  - [`platform.<platform>`](#platformplatform)
  - [`executable`](#executable)
  - [`destination`](#destination)
  - [`extract`](#extract)
  - [`extract.globs`](#extractglobs)
  - [`extract.flatten`](#extractflatten)
- [Commands](#commands)
  - [`lock`](#lock)
  - [`install`](#install)
  - [`list`](#list)
  - [Common Arguments](#common-arguments)

---

## Overview

The `dev_scripts/inventory.py` tool is a Python script designed to manage assets
from GitHub releases. It expects a configuration file (in TOML format) that
contains a list of assets and some parameters. Using this config file, it can
query GitHub for release information, compute checksums for assets, update a
lock file (JSON format) and install assets as described in the lock file.

If you come from a Python background, think of it like "Poetry, but for GitHub
assets".

## Configuration

Before you begin working with the script, you must create a configuration file
in one of the following locations of your project:
* `inventory.toml`: This is a config file written specifically for this tool.
* `pyproject.toml`: This is a config file written for a Python project. The
  inventory tool expects a `[tool.inventory]` section in this file.

### Examples

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

### `repo`

**Type:** `string`

The GitHub repository identifier in the format `"owner/repo"`.

### `version`

**Type:** `string`

A semantic versioning (semver) expression specifying the release version
constraint for the asset, such as `">=1.0.1"`, `"==2.0.0"`
([options](https://python-semver.readthedocs.io/en/latest/usage/compare-versions-through-expression.html)).

### `platform.<platform>`

**Type:** `string`

The filename of an asset for a specific platform, since assets may have
different filenames per platform.

Allowed argument names:
* Strings like `platform."windows/amd64"`, `platform."linux/amd64"`,
  `platform."darwin/arm64"`.
* `platform.all`, for platform-agnostic assets, i.e., assets that should be
  installed regardless of the platform type.

Allowed values:
* Strings like `asset-linux-amd64`, `foo-0.1.0.zip`
* Template strings like `foo-{version}.zip`, where `{version}` will be replaced
  during install time with the version of the asset (minus the leading `v`)
* Special strings `"!tarball"` or `"!zipball"`, to get the GitHub-generated
  source archives for a release.

### `executable`

**Type:** `boolean`

**Default:** `false`

Indicates whether the downloaded asset should be marked as executable.

### `destination`

**Type:** `string`

The local path where the asset should be installed. If the asset is a file, the
destination will be its filename. Else, it will be the directory where the
contents will be extracted in.

### `extract`

**Type:** `boolean | list of strings | dict`

**Default:** `false`

Extraction options for zip/tar files. By default no extraction will take place.
If set to `true`, then the contents of the archive will be extracted to the
destination. If a list of globs is provided, only the matching filenames in the
archive will be extracted.

See [`extract.globs`](#extractglobs) and [`extract.flatten`](#extractflatten)
for more info.

### `extract.globs`

**Type:** `list of strings`

**Default:** `["*"]`

A list of glob strings to match specific files from an archive. Accepted values
are any valid glob such as `*.exe`, `bin/**/asset`
([options](https://docs.python.org/3/library/fnmatch.html)). Will extract all
files in the archive if omitted.

### `extract.flatten`

**Type:** `boolean`

**Default:** `false`

Indicates whether the contents of the archive should be copied to the
destination root. By default the file hierarchy in the archive is preserved.

## Commands

The inventory script supports three commands:
- `lock`
- `install`
- `list`

The following sections assume you invoke the script with `poetry run`.

### `lock`

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

### `install`

The `install` command installs (downloads or copies) assets as specified in the
lock file for the given platform (or the current platform if none is provided).
It downloads assets into a cache, verifies them against an expected hash, copies
them to the destination, marks files as executable if required, and extracts
files based on the provided extraction criteria.

Examples:

Install all assets for the current platform:

```
./dev_scripts/inventory.py install
Installing 'asset1'
Installing 'asset2'
Installed 2 assets.
```

Install all assets for the provided platform:

```
./dev_scripts/inventory.py install -p darwin/amd64
Installing 'asset3'
Installed 1 assets.
```

Install only specific assets:

```
./dev_scripts/inventory.py install asset1
Installing 'asset1'
Installed 1 assets.
```

### `list`

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

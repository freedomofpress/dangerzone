# Inventory Tool Developer Documentation

This document describes how to run the Inventory tool, what each command does, and provides details on the supported configuration fields in the inventory TOML file.

---

## Table of Contents

- [Overview](#overview)
- [Running the Script](#running-the-script)
  - [Commands Overview](#commands-overview)
    - [lock](#lock)
    - [sync](#sync)
    - [list](#list)
  - [Examples](#examples)
- [inventory.toml Format Specification](#inventorytoml-format-specification)
  - [General Structure](#general-structure)
  - [Fields Description](#fields-description)

---

## Overview

The Inventory tool is a Python script designed to manage asset versions from GitHub repositories. It can query GitHub for release information, compute checksums for assets, update a lock file (JSON format) and sync assets as described in a configuration file (in TOML format).

The main script supports three commands:
- `lock`
- `sync`
- `list`

---

## Running the Script

### Commands Overview

#### lock

The `lock` command updates the lock file based on the configuration defined in `config.toml`. For each asset, it reads configuration details, queries GitHub to find the appropriate release and asset URL, computes a checksum if the asset is available locally, uses caching for fetching and hashing, renders filenames that contain `{version}`, and supports assets that are platform-agnostic using `platform.all`.

Usage Example:
```
python inventory.py lock -C /path/to/config --verbose
```

#### sync

The `sync` command synchronizes (downloads or copies) assets as specified in the lock file for the given platform (or the current platform if none is provided). It downloads assets into a cache, verifies them against an expected hash, copies them to the destination, marks files as executable if required, and extracts files based on the provided extraction criteria.

Usage Example for syncing all assets:
```
python inventory.py sync -p linux/amd64
```
Usage Example for syncing only specific assets:
```
python inventory.py sync asset1 asset2 -p windows/amd64
```

#### list

The `list` command lists all assets stored in the lock file along with their version numbers and download URLs for a specified or detected platform.

Usage Example:
```
python inventory.py list -p darwin/arm64
```

### Common Arguments

Each command supports the following optional arguments:

- `-p, --platform`:
  Specify the platform for which the assets should be processed. Examples include:
  `windows/amd64`, `linux/amd64`, `darwin/amd64`, `darwin/arm64`.
  If not provided, the current platform is auto-detected.

- `-v, --verbose`:
  Enable verbose logging. Use `-v` for INFO level or `-vv` (or more) for DEBUG level messaging.

- `-C, --directory`:
  Specify the working directory for the script. Defaults to the current working directory if not provided.

---

## inventory.toml Format Specification

### General Structure

Each asset is defined as an entry under the `[asset]` section. For example:

```toml
[asset.myAsset]
repo = "owner/repo"
version = ">=1.0.1"
platform."windows/amd64" = "asset-windows.exe"
platform."linux/amd64"   = "asset-linux"
platform.all             = "universal-asset.zip"
executable = true
destination = "./downloads/asset.exe"
extract = false
```

### Fields Description

The table below lists the configuration fields supported for each asset entry along with their possible values.

| Field         | Description                                                                                                                                                      | Possible Values                                                                                                                                                                                                         |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| repo          | The GitHub repository identifier in the format `"owner/repo"`.                                                                                                   | Any valid GitHub repository string (e.g., `"octocat/Hello-World"`).                                                                                                        |
| version       | A semantic versioning (semver) expression specifying the release version constraint for the asset.                                                               | Any valid semver expression, such as `">=1.0.1"`, `"=2.0.0"`, `"~1.2"`.                                                                                                     |
| Platform keys | Define the asset file for specific platforms. Assets may have different filenames per platform. A fallback `platform.all` key can be used for platform-agnostic assets. | Keys like `platform."windows/amd64"`, `platform."linux/amd64"`, `platform."darwin/arm64"`; **Fallback Key:** `platform.all`. The value is the filename as a string. Templates with `{version}` are allowed. |
| executable    | Indicates whether the downloaded asset should be marked as executable.                                                                                           | `true` or `false`.                                                                                                                                                                                                     |
| destination   | The local file path where the asset should be saved after download.                                                                                              | Any valid file path string (e.g., `"./downloads/asset.exe"`).                                                                                                                                                           |
| extract       | Instructions for file extraction from the downloaded asset.                                                                                                    | `false` (or omitted) for no extraction; a list of glob strings (e.g., `[ "*.exe", "*.dll" ]`) to extract matching files; or a table with keys `globs` (list of glob strings) and `flatten` (`true` or `false`).  |

---

## Summary

The Inventory tool automates dependency and version management by syncing assets from GitHub using a configuration file (`inventory.toml`) and creating a lock file. It provides three commands—`lock`, `sync`, and `list`—each accommodating platform-specific behavior, verbosity options, and custom working directories. The configuration file offers flexibility with platform-specific asset definitions and extraction behavior, making it a versatile component for asset management in development workflows.

For further details or contributions, please refer to the source code comments and inline documentation.

#!/usr/bin/env python3
"""
GitHub assets inventory

This script keeps an inventory of assets (currently GitHub release assets) in a TOML
file, resolves their versions (via GitHub API and semver ranges), calculates file
checksums, and downloads assets based on a JSON “lock” file.
"""

import argparse
import fnmatch
import hashlib
import json
import os
import platform
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path

import requests
import semver
import toml
from platformdirs import user_cache_dir

# CONSTANTS
CONFIG_FILE = "inventory.toml"
LOCK_FILE = "inventory.lock"
GITHUB_API_URL = "https://api.github.com"

# Determine the cache directory using platformdirs
CACHE_ROOT = Path(user_cache_dir("gh_assets_manager"))


# HELPER FUNCTIONS
def read_config():
    try:
        with open(CONFIG_FILE, "r") as fp:
            return toml.load(fp)
    except Exception as e:
        print(f"Could not load configuration file: {e}")
        sys.exit(1)


def check_lock_stale(lock):
    config = read_config()
    config_hash = hashlib.sha256(json.dumps(config).encode()).hexdigest()
    if config_hash != lock["config_checksum"]:
        raise Exception(
            "You have made changes to the inventory since you last updated the lock"
            " file. You need to run the 'lock' command again."
        )


def write_lock(lock_data):
    with open(LOCK_FILE, "w") as fp:
        json.dump(lock_data, fp, indent=2)


def load_lock(check=True):
    try:
        with open(LOCK_FILE, "r") as fp:
            lock = json.load(fp)
            if check:
                check_lock_stale(lock)
            return lock
    except Exception as e:
        print(f"Could not load lock file: {e}")
        sys.exit(1)


def calc_checksum(stream):
    """
    Calculate a SHA256 hash of a binary stream by reading 1MiB intervals.
    """
    h = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024**3), b""):
        h.update(chunk)
    return h.hexdigest()


def cache_file_path(url):
    """
    Generate a safe cache file path for a given URL,
    using sha256(url) as filename.
    """
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    return CACHE_ROOT / url_hash


def store_checksum_in_cache(url, checksum):
    """Store the checksum in a file whose name is based on the URL hash."""
    checksum_path = cache_file_path(url).with_suffix(".sha256")
    with open(checksum_path, "w") as fp:
        fp.write(checksum)


def read_checksum_from_cache(url):
    checksum_path = cache_file_path(url).with_suffix(".sha256")
    if checksum_path.exists():
        return checksum_path.read_text().strip()
    return None


def get_cached_url(url):
    """
    If the URL exists in our local cache, return the file path;
    otherwise return None.
    """
    file_path = cache_file_path(url)
    if file_path.exists():
        return file_path
    return None


def download_to_cache(url):
    """
    Download an asset from the given URL to the cache directory.
    If the asset already exists in the cache, return its path.
    Otherwise, download it, store a parallel .sha256 (with the computed hash)
    and return its path.
    """
    cached = get_cached_url(url)
    if cached:
        return cached

    print(f"Downloading {url} into cache...")
    response = requests.get(url, stream=True)
    response.raise_for_status()

    cached = cache_file_path(url)
    with open(cached, "wb") as f:
        shutil.copyfileobj(response.raw, f)
    # Calculate and store checksum in cache
    with open(cached, "rb") as f:
        checksum = calc_checksum(f)
    store_checksum_in_cache(url, checksum)
    print("Download to cache completed.")
    return cached


def detect_platform():
    # Return a string like 'windows/amd64' or 'linux/amd64' or 'darwin/amd64'
    sys_platform = sys.platform
    if sys_platform.startswith("win"):
        os_name = "windows"
    elif sys_platform.startswith("linux"):
        os_name = "linux"
    elif sys_platform.startswith("darwin"):
        os_name = "darwin"
    else:
        os_name = sys_platform

    machine = platform.machine().lower()
    # Normalize architecture names
    arch = {"x86_64": "amd64", "amd64": "amd64", "arm64": "arm64"}.get(machine, machine)
    return f"{os_name}/{arch}"


def get_latest_release(repo, semver_range):
    """
    Query the GitHub API for repo releases, parse semver, and choose the
    latest release matching the given semver_range string (e.g., ">=1.0.1", "==1.2.2").
    """
    url = f"{GITHUB_API_URL}/repos/{repo}/releases"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to fetch releases for repo {repo}. HTTP {response.status_code}")
        return None
    releases = response.json()

    matching = []
    for release in releases:
        tag = release.get("tag_name", "")
        # Strip any prefix 'v' if necessary
        version_str = tag.lstrip("v")
        try:
            version = semver.VersionInfo.parse(version_str)
            # Skip prereleases and non-matching versions
            if release["prerelease"] or not version.match(semver_range):
                continue
            matching.append((release, version))
        except ValueError:
            continue

    if not matching:
        print(f"No releases match version requirement {semver_range} for repo {repo}")
        return None

    return max(matching, key=lambda x: x[1])[0]


def resolve_asset_for_platform(release, name):
    """
    Given the release JSON and an asset name, find the asset download URL by matching
    filename.  If the asset name contains "{version}", it will be formatted using the
    release tag.
    """
    if name == "!tarball":
        return release["tarball_url"]
    elif name == "!zipball":
        return release["zipball_url"]

    # Format the name with the found version, in case it requires it.
    version = release.get("tag_name").lstrip("v")
    expected_name = name.format(version=version)

    assets = release.get("assets", [])
    for asset in assets:
        if asset.get("name") == expected_name:
            return asset.get("browser_download_url")
    return None


def hash_asset(url):
    """
    Download the asset using caching and return its SHA256 checksum.
    The checksum is also stored in the cache as a .sha256 file.
    """
    cached_file = download_to_cache(url)
    with open(cached_file, "rb") as f:
        checksum = calc_checksum(f)
    store_checksum_in_cache(url, checksum)
    return checksum


def download_to_cache_and_verify(url, destination, expected_checksum):
    """
    Using caching, first download an asset to the cache dir.
    Verify its checksum against the expected_checksum.
    If they match, copy to destination.
    If not, remove the cached file and raise an exception.
    """
    cached_file = download_to_cache(url)
    with open(cached_file, "rb") as f:
        computed_checksum = calc_checksum(f)

    if computed_checksum != expected_checksum:
        # Remove cache file and its checksum file
        try:
            cached_file.unlink()
            checksum_file = cached_file.with_suffix(".sha256")
            if checksum_file.exists():
                checksum_file.unlink()
        except Exception:
            pass
        raise Exception(
            f"Hash mismatch for URL {url}: computed '{computed_checksum}', expected '{expected_checksum}'"
        )
    return cached_file


def determine_extract_opts(extract):
    """
    Determine globs and flatten settings.
    """
    if isinstance(extract, dict):
        globs = extract.get("globs", ["*"])
        flatten = extract.get("flatten", False)
    elif isinstance(extract, list):
        globs = extract
        flatten = False
    elif isinstance(extract, bool):
        globs = ["*"]
        flatten = False
    else:
        raise Exception(f"Unexpected format for 'extract' field: {extract}")

    return {
        "globs": globs,
        "flatten": flatten,
    }


def detect_archive_type(name):
    """
    Detect the filetype of the archive based on its name.
    """
    if name.endswith(".tar.gz") or name.endswith(".tgz") or name == "!tarball":
        return "tar.gz"
    if name.endswith(".tar"):
        return "tar"
    if name.endswith(".zip") or name == "!zipball":
        return "zip"
    raise Exception(f"Unsupported archive type for extraction: {name}")


def flatten_extracted_files(destination):
    """
    After extraction, move all files found in subdirectories of destination into destination root.
    """
    for root, dirs, files in os.walk(destination):
        # Skip the root directory itself
        if Path(root) == destination:
            continue
        for file in files:
            src_file = Path(root) / file
            dst_file = destination / file
            # If a file with the same name exists, we can overwrite or rename.
            shutil.move(str(src_file), str(dst_file))
    # Optionally, remove now-empty subdirectories.
    for root, dirs, files in os.walk(destination, topdown=False):
        for d in dirs:
            dir_path = Path(root) / d
            try:
                dir_path.rmdir()
            except OSError:
                pass


def extract_asset(archive_path, destination, options):
    """
    Extract the asset from archive_path to destination.

    Accepts a dictionary withe the following options:
    * 'globs': A list of patterns that will be used to match members in the archive.
      If a member does not match a pattern, it will not be extracted.
    * 'flatten': A boolean value. If true, after extraction, move all files to the
       destination root.
    * 'filetype': The type of the archive, which indicates how it will get extracted.

    For tarfiles, use filter="data" when extracting to mitigate malicious tar entries.
    """
    ft = options["filetype"]
    globs = options["globs"]
    flatten = options["flatten"]

    if ft in ("tar.gz", "tar"):
        mode = "r:gz" if ft == "tar.gz" else "r"
        try:
            with tarfile.open(archive_path, "r:gz") as tar:
                members = [
                    m
                    for m in tar.getmembers()
                    if any(fnmatch.fnmatch(m.name, glob) for glob in globs)
                ]
                if not members:
                    raise Exception("Globs did not match any files in the archive")
                tar.extractall(path=destination, members=members, filter="data")
        except Exception as e:
            raise Exception(f"Error extracting '{archive_path}': {e}")
    elif ft == "zip":
        try:
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                members = [
                    m
                    for m in zip_ref.namelist()
                    if any(fnmatch.fnmatch(m, glob) for glob in globs)
                ]
                if not members:
                    raise Exception("Globs did not match any files in the archive")
                zip_ref.extractall(path=destination, members=members)
        except Exception as e:
            raise Exception(f"Error extracting zip archive: {e}")
    else:
        raise Exception(f"Unsupported archive type for file {archive_path}")

    if flatten:
        flatten_extracted_files(destination)

    print(f"Extraction of {archive_path} complete.")


def get_platform_assets(assets, platform):
    """
    List the assets that are associated with a specific platform.
    """

    plat_assets = {}
    for asset_name, asset_entry in assets.items():
        if platform in asset_entry:
            plat_assets[asset_name] = asset_entry[platform]
        elif "all" in asset_entry:
            plat_assets[asset_name] = asset_entry["all"]
    return plat_assets


def chmod_exec(path):
    if path.is_dir():
        for root, _, files in path.walk():
            for name in files:
                f = root / name
                f.chmod(f.stat().st_mode | 0o111)
    else:
        path.chmod(path.stat().st_mode | 0o111)


# COMMAND FUNCTIONS
def cmd_lock(args):
    """
    Reads the configuration file, queries GitHub for each asset to determine
    the actual release and asset URL, calculates checksum if the asset exists locally.
    Then outputs/updates the lock file (in JSON format).

    Changes:
      - Uses "destination" instead of "download_path" in the config.
      - Uses caching when fetching/hashing assets.
      - Renders asset filenames if they contain {version}.
      - Supports a 'platform.all' key for platform-agnostic assets.
    """
    config = read_config()
    lock = {"assets": {}}
    # Expected config structure in config.toml:
    # [asset.<asset_name>]
    #   repo = "owner/repo"
    #   version = ">=1.0.1"  # semver expression
    #   platform."windows/amd64" = "asset-windows.exe"
    #   platform."linux/amd64"   = "asset-linux"
    #   platform.all             = "universal-asset.zip"
    #   executable = true|false  # whether to mark downloaded file as executable
    #   destination = "./downloads/asset.exe"
    #   extract = either false, a list of globs,
    #             or a table with keys: globs = ["glob1", "glob2"]
    #             and flatten = True|False.
    assets_cfg = config.get("asset", {})
    if not assets_cfg:
        print("No assets defined under the [asset] section in the config file.")
        sys.exit(1)

    for asset_name, asset in assets_cfg.items():
        repo = asset.get("repo")
        version_range = asset.get("version")
        asset_map = asset.get("platform")  # mapping platform -> asset file name
        executable = asset.get("executable")
        destination_str = asset.get("destination")
        extract = asset.get("extract", False)

        if extract:
            extract = determine_extract_opts(extract)

        if not repo or not version_range or not asset_map or not destination_str:
            print(f"Asset {asset_name} is missing required fields.")
            continue

        print(f"Processing asset '{asset_name}' for repo '{repo}' ...")
        release = get_latest_release(repo, version_range)
        if not release:
            print(f"Could not resolve release for asset '{asset_name}'.")
            continue

        lock_assets = lock["assets"]
        asset_lock_data = {}
        # Process each defined platform key in the asset_map
        for plat_key, plat_name in asset_map.items():
            download_url = resolve_asset_for_platform(release, plat_name)
            if not download_url:
                print(
                    f"Warning: No asset found for platform '{plat_key}' in repo '{repo}' for asset '{asset_name}'."
                )
                continue

            if extract:
                extract = extract.copy()
                extract["filetype"] = detect_archive_type(plat_name)
            print(f"Hashing asset '{asset_name}' for platform '{plat_key}'...")
            checksum = hash_asset(download_url)
            asset_lock_data[plat_key] = {
                "repo": repo,
                "download_url": download_url,
                "version": release.get("tag_name").lstrip("v"),
                "checksum": checksum,
                "executable": executable,
                "destination": destination_str,
                "extract": extract,
            }
        if not asset_lock_data:
            print(f"No valid platforms found for asset '{asset_name}'.")
            continue
        lock_assets[asset_name] = asset_lock_data

    config_hash = hashlib.sha256(json.dumps(config).encode()).hexdigest()
    lock["config_checksum"] = config_hash
    write_lock(lock)
    print(f"Lock file '{LOCK_FILE}' updated.")


def cmd_sync(args):
    """
    Sync assets based on the lock file. Accepts an optional platform argument
    to limit downloads and an optional list of asset names.

    Features:
      - Uses caching: downloads happen into the cache, then verified against the expected hash,
        and finally copied to the destination.
      - If executable field is set, mark the downloaded file(s) as executable.
      - If extract field is set:
          o If False or missing: no extraction, just copy.
          o Otherwise, if extract is set:
               - If extract is a list, treat it as a list of globs.
               - If extract is a table, expect keys "globs" and optional "flatten".
      - For platform-agnostic assets, an entry with key "platform.all" is used if the requested
        platform is not found.
    """
    lock = load_lock()
    target_plat = args.platform if args.platform else detect_platform()
    print(f"Target platform: {target_plat}")
    lock_assets = lock["assets"]
    asset_list = (
        args.assets
        if args.assets
        else get_platform_assets(lock_assets, target_plat).keys()
    )

    # Validate asset names and platform entries
    for asset_name in asset_list:
        if asset_name not in lock_assets:
            raise Exception(f"Asset '{asset_name}' not found in the lock file.")
        asset_entry = lock_assets[asset_name]

        # If an asset.entry contains "platform.all", then we should fallback to that, if
        # the specific platform we're looking for is not defined.
        if target_plat not in asset_entry:
            if "all" in asset_entry:
                target_plat = "all"
            else:
                raise Exception(
                    f"No entry for platform '{target_plat}' or 'platform.all' in asset"
                    f" '{asset_name}'"
                )

        info = asset_entry[target_plat]
        download_url = info["download_url"]
        destination = Path(info["destination"])
        expected_checksum = info["checksum"]
        executable = info["executable"]
        extract = info.get("extract", False)
        try:
            print(f"Processing asset '{asset_name}' for platform '{target_plat}'...")
            cached_file = download_to_cache_and_verify(
                download_url, destination, expected_checksum
            )
            # Remove destination if it exists already.
            if destination.exists():
                if destination.is_dir():
                    shutil.rmtree(destination)
                else:
                    destination.unlink()
            # If extraction is requested
            if extract:
                destination.mkdir(parents=True, exist_ok=True)
                filename = download_url.split("/")[-1]
                extract_asset(
                    cached_file,
                    destination,
                    options=extract,
                )
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(cached_file, destination)
            if executable:
                chmod_exec(destination)
        except Exception as e:
            print(
                f"Error processing asset '{asset_name}' for platform '{target_plat}': {e}"
            )
            continue

    print("Downloads completed")


def cmd_list(args):
    """
    List assets and their versions based on the lock file and the provided platform. If
    a platform is not provided, list assets for the current one.
    """
    lock = load_lock()
    target_plat = args.platform if args.platform else detect_platform()
    assets = get_platform_assets(lock["assets"], target_plat)
    for asset_name in sorted(assets.keys()):
        asset = assets[asset_name]
        print(f"{asset_name} {asset['version']} {asset['download_url']}")


def main():
    parser = argparse.ArgumentParser(description="GitHub Release Assets Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    lock_parser = subparsers.add_parser(
        "lock", help="Update lock file from config (without downloading)"
    )
    lock_parser.set_defaults(func=cmd_lock)

    sync_parser = subparsers.add_parser("sync", help="Sync assets as per lock file")
    sync_parser.add_argument(
        "--platform",
        help="Platform name/arch (e.g., windows/amd64) to download assets for",
    )
    sync_parser.add_argument(
        "assets",
        nargs="*",
        help="Specific asset names to download. If omitted, download all assets.",
    )
    sync_parser.set_defaults(func=cmd_sync)

    list_parser = subparsers.add_parser("list", help="List assets for a platform")
    list_parser.add_argument(
        "--platform",
        help="Platform name/arch (e.g., windows/amd64) to list assets for",
    )
    list_parser.set_defaults(func=cmd_list)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

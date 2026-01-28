#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import contextlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# .absolute() is needed for python<=3.8, for which
# __file__ returns an absolute path.
root = Path(__file__).parent.parent.parent.absolute()

with open(root / "share" / "version.txt") as f:
    version = f.read().strip()


def run(cmd):
    subprocess.run(cmd, cwd=root, check=True)


@contextlib.contextmanager
def exclude_paths(paths):
    """Temporarily exclude paths by renaming them."""
    backup_paths = [p.parents[1] / (p.name + ".bak") for p in paths]
    for path, backup in zip(paths, backup_paths):
        if path.exists():
            path.rename(backup)
    try:
        yield
    finally:
        for path, backup in zip(paths, backup_paths):
            if backup.exists():
                backup.rename(path)


@contextlib.contextmanager
def full_debian_files():
    """Temporarily modify debian files for full package build (with container.tar)."""
    control_path = root / "debian" / "control"
    changelog_path = root / "debian" / "changelog"
    rules_path = root / "debian" / "rules"

    control_orig = control_path.read_text()
    changelog_orig = changelog_path.read_text()
    rules_orig = rules_path.read_text()

    control_new = (
        control_orig.replace("Source: dangerzone", "Source: dangerzone-full")
        .replace("Package: dangerzone", "Package: dangerzone-full")
        .replace(
            "Conflicts: dangerzone-full, dangerzone-qubes",
            "Conflicts: dangerzone, dangerzone-qubes",
        )
    )

    changelog_new = re.sub(
        r"^dangerzone \(", "dangerzone-full (", changelog_orig, flags=re.MULTILINE
    )

    rules_new = rules_orig.replace(
        "export PYBUILD_NAME=dangerzone", "export PYBUILD_NAME=dangerzone-full"
    ).replace("debian/dangerzone/", "debian/dangerzone-full/")

    try:
        control_path.write_text(control_new)
        changelog_path.write_text(changelog_new)
        rules_path.write_text(rules_new)
        yield
    finally:
        control_path.write_text(control_orig)
        changelog_path.write_text(changelog_orig)
        rules_path.write_text(rules_orig)


def main():
    parser = argparse.ArgumentParser(
        prog=sys.argv[0],
        description="Dev script for building Dangerzone debs",
    )
    # FIXME: The name of the distro is important, as it can help users who are upgrading
    # from a distro version to another. If we *do* need to provide a name at some point,
    # here's a suggestion on how we should tackle naming:
    #
    # https://github.com/freedomofpress/dangerzone/pull/322#issuecomment-1428665162
    parser.add_argument(
        "--distro",
        required=False,
        help="The name of the Debian-based distro",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Build DEB package with container.tar bundled",
    )
    args = parser.parse_args()

    dist_path = root / "dist"
    deb_dist_path = root / "deb_dist"

    print("* Deleting old dist and deb_dist")
    if os.path.exists(dist_path):
        shutil.rmtree(dist_path)
    if os.path.exists(deb_dist_path):
        shutil.rmtree(deb_dist_path)

    print("* Building DEB package")
    if args.distro is None:
        deb_ver = "1"
    else:
        deb_ver = args.distro

    if args.full:
        # Full package: includes container.tar
        pkg_name = "dangerzone-full"
        with full_debian_files():
            run(["dpkg-buildpackage"])
    else:
        # Default package: does NOT include container.tar
        pkg_name = "dangerzone"
        with exclude_paths([root / "share" / "container.tar"]):
            run(["dpkg-buildpackage"])

    os.makedirs(deb_dist_path, exist_ok=True)
    print("")
    print("* To install run:")

    # dpkg-buildpackage produces a .deb file in the parent folder
    # that needs to be copied to the `deb_dist` folder manually
    src = root.parent / f"{pkg_name}_{version}_amd64.deb"
    destination = root / "deb_dist" / f"{pkg_name}_{version}-{deb_ver}_amd64.deb"
    shutil.move(src, destination)
    print(f"sudo dpkg -i {destination}")


if __name__ == "__main__":
    main()

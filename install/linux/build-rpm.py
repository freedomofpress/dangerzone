#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import inspect
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).parent.parent.parent

with open(os.path.join(root, "share", "version.txt")) as f:
    version = f.read().strip()


def remove_contents(d):
    """Remove all the contents of a directory."""
    for p in d.iterdir():
        if p.is_file() or p.is_symlink():
            p.unlink()
        else:
            shutil.rmtree(p)


def build(build_dir, qubes=False):
    """Build an RPM package in a temporary directory.

    The build process is the following:

    1. Clean up any stale data from previous runs under ./dist. Note that this directory
       is used by `poetry build` and `rpmbuild`.
    2. Create the necessary RPM project structure under the specified build directory
       (default: ~/rpmbuild), and use symlinks to point to ./dist, so that we don't need
       to move files explicitly.
    3. Create a Python source distribution using `poetry build`. If we are building a
       Qubes package and there is a container image under `share/`, stash it temporarily
       under a different directory.
    4. Build both binary and source RPMs using rpmbuild. Optionally, pass to the SPEC
        `_qubes` flag, that denotes we want to build a package for Qubes.
    """
    dist_path = root / "dist"
    specfile_name = "dangerzone.spec"
    specfile_path = root / "install" / "linux" / specfile_name
    sdist_name = f"dangerzone-{version}.tar.gz"
    sdist_path = dist_path / sdist_name

    print("* Deleting old dist")
    if os.path.exists(dist_path):
        remove_contents(dist_path)
    else:
        dist_path.mkdir()

    print(f"* Creating RPM project structure under {build_dir}")
    build_dir.mkdir(exist_ok=True)
    for d in ["BUILD", "BUILDROOT", "RPMS", "SOURCES", "SPECS"]:
        subdir = build_dir / d
        subdir.mkdir(exist_ok=True)
        remove_contents(subdir)

    shutil.copy2(specfile_path, build_dir / "SPECS")
    rpm_dir = build_dir / "RPMS" / "x86_64"
    srpm_dir = build_dir / "SRPMS"
    srpm_dir.unlink(missing_ok=True)
    os.symlink(dist_path, rpm_dir)
    os.symlink(dist_path, srpm_dir)

    print("* Creating a Python sdist")
    container_tar_gz = root / "share" / "container.tar.gz"
    container_tar_gz_bak = root / "container.tar.gz.bak"
    stash_container = qubes and container_tar_gz.exists()
    if stash_container:
        container_tar_gz.rename(container_tar_gz_bak)
    try:
        subprocess.run(["poetry", "build", "-f", "sdist"], cwd=root, check=True)
        # Copy and unlink the Dangerzone sdist, instead of just renaming it. If the
        # build directory is outside the filesystem boundary (e.g., due to a container
        # mount), then a simple rename will not work.
        shutil.copy2(sdist_path, build_dir / "SOURCES" / sdist_name)
        sdist_path.unlink()
    finally:
        if stash_container:
            container_tar_gz_bak.rename(container_tar_gz)

    print("* Building RPM package")
    cmd = [
        "rpmbuild",
        "-v",
        "--define",
        f"_topdir {build_dir}",
        "-ba",
        "--nodebuginfo",
        f"{build_dir}/SPECS/dangerzone.spec",
    ]

    # In case of qubes, set the `%{_qubes}` SPEC variable to 1. See the dangerzone.spec
    # file for more details on how that's used.
    if qubes:
        cmd += [
            "--define",
            f"_qubes 1",
        ]
    subprocess.run(cmd, check=True)

    print("")
    print("The following files have been created:")
    print("\n".join([str(p) for p in dist_path.iterdir()]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--qubes", action="store_true", help="Build RPM package for a Qubes OS system"
    )
    parser.add_argument(
        "--build-dir",
        default=Path.home() / "rpmbuild",
        help="Working directory for rpmbuild command",
    )
    args = parser.parse_args()

    build(args.build_dir, args.qubes)


if __name__ == "__main__":
    main()

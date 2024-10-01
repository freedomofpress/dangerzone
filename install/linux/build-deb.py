#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
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

    run(
        [
            "dpkg-buildpackage",
        ]
    )

    os.makedirs(deb_dist_path, exist_ok=True)
    print("")
    print("* To install run:")

    # dpkg-buildpackage produces a .deb file in the parent folder
    # that needs to be copied to the `deb_dist` folder manually
    src = root.parent / f"dangerzone_{version}_amd64.deb"
    destination = root / "deb_dist" / f"dangerzone_{version}-{deb_ver}_amd64.deb"
    shutil.move(src, destination)
    print(f"sudo dpkg -i {destination}")


if __name__ == "__main__":
    main()

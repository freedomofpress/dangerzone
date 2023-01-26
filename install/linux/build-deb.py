#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import inspect
import os
import shutil
import subprocess
import sys

root = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
    )
)

with open(os.path.join(root, "share", "version.txt")) as f:
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

    dist_path = os.path.join(root, "dist")
    deb_dist_path = os.path.join(root, "deb_dist")

    print("* Deleting old dist and deb_dist")
    if os.path.exists(dist_path):
        shutil.rmtree(dist_path)
    if os.path.exists(deb_dist_path):
        shutil.rmtree(deb_dist_path)

    print("* Building DEB package")
    # NOTE: This command first builds the Debian source package, and then creates the
    # final DEB package. We could simply call `bdist_deb`, which performs `sdist_dsc`
    # implicitly, but we wouldn't be able to pass the Debian version argument. Because
    # we do this in a single invocation though, there's no performance cost.
    if args.distro is None:
        deb_ver_args = ()
        deb_ver = "1"
    else:
        deb_ver_args = ("--debian-version", args.distro)
        deb_ver = args.distro

    run(
        [
            "python3",
            "setup.py",
            "--command-packages=stdeb.command",
            "sdist_dsc",
            *deb_ver_args,
            "bdist_deb",
        ]
    )

    print("")
    print("* To install run:")
    print(f"sudo dpkg -i deb_dist/dangerzone_{version}-{deb_ver}_all.deb")


if __name__ == "__main__":
    main()

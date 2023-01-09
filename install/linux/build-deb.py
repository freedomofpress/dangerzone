#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
    dist_path = os.path.join(root, "dist")
    deb_dist_path = os.path.join(root, "deb_dist")

    print("* Deleting old dist and deb_dist")
    if os.path.exists(dist_path):
        shutil.rmtree(dist_path)
    if os.path.exists(deb_dist_path):
        shutil.rmtree(deb_dist_path)

    print("* Building DEB package")
    # This command also builds the Debian source package, and then creates the DEB
    # package, meaning that we don't need to run `sdist_dsc` as well.
    run(["python3", "setup.py", "--command-packages=stdeb.command", "bdist_deb"])

    print("")
    print("* To install run:")
    print("sudo dpkg -i deb_dist/dangerzone_{}-1_all.deb".format(version))


if __name__ == "__main__":
    main()

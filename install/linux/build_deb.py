#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import inspect
import subprocess
import shutil

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
import dangerzone

version = dangerzone.dangerzone_version
root = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
    )
)


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
    run(["python3", "setup.py", "--command-packages=stdeb.command", "bdist_deb"])
    run(["python3", "setup.py", "--command-packages=stdeb.command", "sdist_dsc"])

    print("")
    print("* To install run:")
    print("sudo dpkg -i deb_dist/dangerzone_{}-1_all.deb".format(version))


if __name__ == "__main__":
    main()

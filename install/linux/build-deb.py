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
    dist_path = root / "dist"
    deb_dist_path = root / "deb_dist"

    print("* Deleting old dist and deb_dist")
    if os.path.exists(dist_path):
        shutil.rmtree(dist_path)
    if os.path.exists(deb_dist_path):
        shutil.rmtree(deb_dist_path)

    print("* Building binary-only DEB package")
    run(["dpkg-buildpackage", "-b"])

    os.makedirs(deb_dist_path, exist_ok=True)
    print("The following files have been created:")
    for src in root.parent.glob(f"dangerzone_{version}*"):
        dest = deb_dist_path / src.name
        shutil.move(src, dest)
        print(f"{dest}")


if __name__ == "__main__":
    main()

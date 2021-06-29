#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import inspect
import subprocess
import shutil


root = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
    )
)

with open(os.path.join(root, "share", "version.txt")) as f:
    version = f.read().strip()


def main():
    build_path = os.path.join(root, "build")
    dist_path = os.path.join(root, "dist")

    print("* Deleting old build and dist")
    if os.path.exists(build_path):
        shutil.rmtree(build_path)
    if os.path.exists(dist_path):
        shutil.rmtree(dist_path)

    print("* Building RPM package")
    subprocess.run(
        "python3 setup.py bdist_rpm --requires='podman,python3-pyside2,python3-appdirs,python3-click,python3-pyxdg,python3-requests,python3-colorama'",
        shell=True,
        cwd=root,
        check=True,
    )

    print("")
    print("* To install run:")
    print("sudo dnf install dist/dangerzone-{}-1.noarch.rpm".format(version))


if __name__ == "__main__":
    main()

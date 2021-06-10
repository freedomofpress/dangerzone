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
        "python3 setup.py bdist_rpm --requires='python3-pyside2,python3-appdirs,python3-click,python3-pyxdg,python3-requests,python3-colorama,(docker or docker-ce)'",
        shell=True,
        cwd=root,
        check=True,
    )

    print("")
    print("* To install run:")
    print("sudo dnf install dist/dangerzone-{}-1.noarch.rpm".format(version))


if __name__ == "__main__":
    main()

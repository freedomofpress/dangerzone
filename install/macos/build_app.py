#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import inspect
import subprocess
import shutil


root = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
    )
)


def run(cmd):
    subprocess.run(cmd, cwd=root, check=True)


def main():
    build_path = os.path.join(root, "build")
    dist_path = os.path.join(root, "dist")
    app_path = os.path.join(dist_path, "Dangerzone.app")

    print("○ Deleting old build and dist")
    if os.path.exists(build_path):
        shutil.rmtree(build_path)
    if os.path.exists(dist_path):
        shutil.rmtree(dist_path)

    print("○ Building app bundle")
    run(["pyinstaller", "install/macos/pyinstaller.spec", "--clean"])
    shutil.rmtree(os.path.join(dist_path, "dangerzone"))

    print("○ Finished: {}".format(app_path))


if __name__ == "__main__":
    main()

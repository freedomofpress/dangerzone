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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--qubes", action="store_true", help="Build RPM package for a Qubes OS system"
    )
    args = parser.parse_args()

    build_path = os.path.join(root, "build")
    dist_path = os.path.join(root, "dist")

    print("* Deleting old build and dist")
    if os.path.exists(build_path):
        shutil.rmtree(build_path)
    if os.path.exists(dist_path):
        shutil.rmtree(dist_path)

    if args.qubes:
        print("> Building for a Qubes system")
        os.environ["QUBES_TARGET"] = "1"

        # Server and Client package requirements are bundled together since
        # we assume the server and client qubes are installed on the same
        # template
        platform_dependant_packages = ",".join(
            [
                # Server package requirements
                "python3-magic",
                "libreoffice",
                # Client package requirements
                "tesseract",  # FIXME add other languages
            ]
        )
    else:
        platform_dependant_packages = "podman"

    print("* Building RPM package")
    subprocess.run(
        f"python3 setup.py bdist_rpm --requires='{platform_dependant_packages},python3-pyside2,python3-appdirs,python3-click,python3-pyxdg,python3-colorama,python3-requests,python3-markdown,python3-packaging'",
        shell=True,
        cwd=root,
        check=True,
    )

    print("")
    print("* To install run:")
    print("sudo dnf install dist/dangerzone-{}-1.noarch.rpm".format(version))


if __name__ == "__main__":
    main()

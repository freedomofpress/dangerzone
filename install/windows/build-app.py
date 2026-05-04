#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build script for Windows installer (.msi).

Supports two variants:
- Default (slim): No container image bundled
- Full (--full): Container image bundled in the package
"""

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

CONTAINER_TAR_PATH = os.path.join(root, "share", "container.tar")


def run(cmd, check=True):
    """Run a command and optionally check for errors."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=root)
    if check and result.returncode != 0:
        print(f"ERROR: Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)
    return result


def main():
    parser = argparse.ArgumentParser(description="Build Dangerzone Windows installer")
    parser.add_argument(
        "--full",
        action="store_true",
        dest="full",
        help="Build with container image bundled (full variant)",
    )
    args = parser.parse_args()

    # Validate container.tar presence based on --full flag
    container_exists = os.path.exists(CONTAINER_TAR_PATH)
    if args.full and not container_exists:
        print(
            f"ERROR: --full requires container.tar at {CONTAINER_TAR_PATH}\n"
            "Run: poetry run ./dev_scripts/dangerzone-image prepare-archive "
            "--image <image> --output share/container.tar"
        )
        sys.exit(1)
    elif not args.full and container_exists:
        print(
            f"ERROR: container.tar found at {CONTAINER_TAR_PATH}\n"
            f"For slim build, remove it first: del {CONTAINER_TAR_PATH}\n"
            "For full build, use: --full"
        )
        sys.exit(1)

    dist_path = os.path.join(root, "dist")
    build_path = os.path.join(root, "build")

    # Delete old dist and build files
    print("○ Deleting old build and dist")
    if os.path.exists(dist_path):
        shutil.rmtree(dist_path)
    if os.path.exists(build_path):
        shutil.rmtree(build_path)

    # Build the GUI and CLI executables
    print("○ Building executables with cx_Freeze")
    run(["python", "setup-windows.py", "build"])

    # Code sign executables
    print("○ Code signing executables")
    run(
        [
            "signtool.exe",
            "sign",
            "/v",
            "/d",
            "Dangerzone",
            "/a",
            "/n",
            "Freedom of the Press Foundation",
            "/fd",
            "sha256",
            "/t",
            "http://time.certum.pl/",
            r"build\exe.win-amd64-3.13\dangerzone.exe",
            r"build\exe.win-amd64-3.13\dangerzone-cli.exe",
            r"build\exe.win-amd64-3.13\dangerzone-image.exe",
            r"build\exe.win-amd64-3.13\dangerzone-machine.exe",
        ]
    )

    # Verify the signatures of the executables
    print("○ Verifying executable signatures")
    run(
        [
            "signtool.exe",
            "verify",
            "/pa",
            r"build\exe.win-amd64-3.13\dangerzone.exe",
            r"build\exe.win-amd64-3.13\dangerzone-cli.exe",
            r"build\exe.win-amd64-3.13\dangerzone-image.exe",
            r"build\exe.win-amd64-3.13\dangerzone-machine.exe",
        ]
    )

    # Build the WiX file
    print("○ Building WiX file")
    run(["python", r"install\windows\build-wxs.py"])

    # Build the MSI package
    print("○ Building MSI package")
    run(
        [
            "wix",
            "build",
            "-arch",
            "x64",
            "-ext",
            "WixToolset.UI.wixext",
            r"build\Dangerzone.wxs",
            "-out",
            r"build\Dangerzone.msi",
        ]
    )

    # Validate Dangerzone.msi
    print("○ Validating MSI package")
    run(["wix", "msi", "validate", r"build\Dangerzone.msi"])

    # Code sign Dangerzone.msi
    print("○ Code signing MSI package")
    run(
        [
            "signtool.exe",
            "sign",
            "/v",
            "/d",
            "Dangerzone",
            "/a",
            "/n",
            "Freedom of the Press Foundation",
            "/fd",
            "sha256",
            "/t",
            "http://time.certum.pl/",
            r"build\Dangerzone.msi",
        ]
    )

    # Verify the signature of Dangerzone.msi
    print("○ Verifying MSI signature")
    run(["signtool.exe", "verify", "/pa", r"build\Dangerzone.msi"])

    # Move Dangerzone.msi to dist
    print("○ Moving MSI to dist folder")
    os.makedirs(dist_path, exist_ok=True)
    shutil.move(os.path.join(build_path, "Dangerzone.msi"), dist_path)

    print(f"○ Finished building MSI: {os.path.join(dist_path, 'Dangerzone.msi')}")


if __name__ == "__main__":
    main()

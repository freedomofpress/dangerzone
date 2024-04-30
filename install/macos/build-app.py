#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import glob
import inspect
import itertools
import os
import shutil
import subprocess
import sys

root = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
    )
)


def run(cmd):
    subprocess.run(cmd, cwd=root, check=True)


def build_app_bundle(build_path, dist_path, app_path):
    """
    Builds the Dangerzone.app bundle and saves it in dist/Dangerzone.app
    """
    print("○ Deleting old build and dist")
    if os.path.exists(build_path):
        shutil.rmtree(build_path)
    if os.path.exists(dist_path):
        shutil.rmtree(dist_path)

    print("○ Building app bundle")
    run(["pyinstaller", "install/pyinstaller/pyinstaller.spec", "--clean"])
    shutil.rmtree(os.path.join(dist_path, "dangerzone"))

    os.symlink(
        "dangerzone",
        os.path.join(app_path, "Contents/MacOS/dangerzone-cli"),
    )

    print(f"○ Finished build app: {app_path}")


def codesign(path, entitlements, identity):
    run(
        [
            "codesign",
            "--sign",
            identity,
            "--entitlements",
            str(entitlements),
            "--timestamp",
            "--deep",
            str(path),
            "--force",
            "--options",
            "runtime",
        ]
    )


def sign_app_bundle(build_path, dist_path, app_path):
    """
    Signs the app bundle stored in dist/Dangerzone.app,
    producing a Dangerzone.dmg file
    """
    print(f"○ Signing app bundle in {app_path}")

    # Detect if create-dmg is installed
    if not os.path.exists(app_path):
        print(f"ERROR: Dangerzone.app not found in {app_path}.")
        sys.exit(1)

    dmg_path = os.path.join(dist_path, "Dangerzone.dmg")
    icon_path = os.path.join(root, "install", "macos", "dangerzone.icns")

    print("○ Code signing app bundle")
    identity_name_application = (
        "Developer ID Application: Freedom of the Press Foundation (94ZZGGGJ3W)"
    )
    entitlements_plist_path = os.path.join(root, "install/macos/entitlements.plist")

    for path in itertools.chain(
        glob.glob(f"{app_path}/**/*.so", recursive=True),
        glob.glob(f"{app_path}/**/*.dylib", recursive=True),
        glob.glob(f"{app_path}/**/Python3", recursive=True),
        [app_path],
    ):
        codesign(path, entitlements_plist_path, identity_name_application)
    print(f"○ Signed app bundle: {app_path}")

    # Detect if create-dmg is installed
    if not shutil.which("create-dmg"):
        print("create-dmg is not installed, skipping creating a DMG")
        return

    print("○ Creating DMG")
    run(
        [
            "create-dmg",
            "--volname",
            "Dangerzone",
            "--volicon",
            icon_path,
            "--window-size",
            "400",
            "200",
            "--icon-size",
            "100",
            "--icon",
            "Dangerzone.app",
            "100",
            "70",
            "--hide-extension",
            "Dangerzone.app",
            "--app-drop-link",
            "300",
            "70",
            dmg_path,
            app_path,
            "--identity",
            identity_name_application,
        ]
    )
    print(f"○ Finished building DMG: {dmg_path}")


def main():
    # Parse arguments
    parser = argparse.ArgumentParser()
    codesign_opts = parser.add_mutually_exclusive_group()
    codesign_opts.add_argument(
        "--with-codesign",
        action="store_true",
        dest="with_codesign",
        help="Codesign the app bundle",
    )
    codesign_opts.add_argument(
        "--only-codesign",
        action="store_true",
        dest="only_codesign",
        help="Exclusively codesign the app bundle in dist/Dangerzone.app",
    )
    args = parser.parse_args()

    build_path = os.path.join(root, "build")
    dist_path = os.path.join(root, "dist")
    app_path = os.path.join(dist_path, "Dangerzone.app")

    if args.only_codesign:
        sign_app_bundle(build_path, dist_path, app_path)
    else:
        build_app_bundle(build_path, dist_path, app_path)
        if args.with_codesign:
            sign_app_bundle(build_path, dist_path, app_path)
        else:
            print("○ Skipping code signing")


if __name__ == "__main__":
    main()

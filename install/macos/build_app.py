#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import inspect
import subprocess
import shutil
import argparse
import glob

root = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
    )
)


def run(cmd):
    subprocess.run(cmd, cwd=root, check=True)


def main():
    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--with-codesign",
        action="store_true",
        dest="with_codesign",
        help="Codesign the app bundle",
    )
    args = parser.parse_args()

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

    print(f"○ Finished build app: {app_path}")

    if args.with_codesign:
        print("○ Code signing app bundle")
        identity_name_application = (
            "Developer ID Application: FIRST LOOK PRODUCTIONS, INC. (P24U45L8P5)"
        )
        entitlements_plist_path = os.path.join(root, "install/macos/entitlements.plist")

        run(
            [
                "codesign",
                "--deep",
                "-s",
                identity_name_application,
                "-o",
                "runtime",
                "--entitlements",
                entitlements_plist_path,
                app_path,
            ]
        )

        # Detect if create-dmg is installed
        if not os.path.exists("/usr/local/bin/create-dmg"):
            print("Error: create-dmg is not installed")
            return

        print("○ Creating DMG")
        run(["create-dmg", app_path, "--identity", identity_name_application])
        dmg_filename = glob.glob(f"{root}/*.dmg")[0]
        shutil.move(dmg_filename, dist_path)
        dmg_filename = glob.glob(f"{dist_path}/*.dmg")[0]

        print(f"○ Finished building DMG: {dmg_filename}")

    else:
        print("○ Skipping code signing")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import inspect
import subprocess
import shutil
import argparse


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
        "--without-codesign",
        action="store_true",
        dest="without_codesign",
        help="Skip codesigning",
    )
    args = parser.parse_args()

    build_path = os.path.join(root, "build")
    dist_path = os.path.join(root, "dist")
    app_path = os.path.join(dist_path, "Dangerzone.app")

    # Make sure Dangerzone.app already exists
    if not os.path.exists(app_path):
        print("○ App bundle doesn't exist yet, should be in: {}".format(app_path))
        return

    # Import dangerzone to get the version
    sys.path.insert(0, root)
    import dangerzone

    version = dangerzone.dangerzone_version

    pkg_path = os.path.join(dist_path, "Dangerzone-{}.pkg".format(version))

    identity_name_application = "Developer ID Application: FIRST LOOK PRODUCTIONS, INC."
    identity_name_installer = "Developer ID Installer: FIRST LOOK PRODUCTIONS, INC."

    if args.without_codesign:
        # Skip codesigning
        print("○ Creating an installer")
        run(
            ["productbuild", "--component", app_path, "/Applications", pkg_path,]
        )

    else:
        # Package with codesigning
        print("○ Codesigning app bundle")
        run(["codesign", "--deep", "-s", identity_name_application, app_path])

        print("○ Creating an installer")
        run(
            [
                "productbuild",
                "--sign",
                identity_name_installer,
                "--component",
                app_path,
                "/Applications",
                pkg_path,
            ]
        )

    print("○ Cleaning up")
    shutil.rmtree(app_path)

    print("○ Finished: {}".format(pkg_path))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
from pathlib import Path

DZ_VENDOR_DIR = Path("./dangerzone/vendor")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dest",
        default=DZ_VENDOR_DIR,
        help="The destination directory for the vendored packages (default: ./dangerzone/vendor)",
    )
    args = parser.parse_args()

    print(">>> Getting PyMuPDF deps as requirements.txt", file=sys.stderr)
    cmd = ["poetry", "export", "--only", "container"]
    container_requirements_txt = subprocess.check_output(cmd)

    # XXX: Hack for Ubuntu Focal.
    if sys.version.startswith("3.8"):
        container_requirements_txt = container_requirements_txt.replace(b"3.9", b"3.8")

    print(f">>> Vendoring PyMuPDF under '{args.dest}'", file=sys.stderr)
    # We prefer to call the CLI version of `pip`, instead of importing it directly, as
    # instructed here:
    # https://pip.pypa.io/en/latest/user_guide/#using-pip-from-your-program
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--no-cache-dir",
        "--no-compile",
        "--target",
        args.dest,
        "--requirement",
        "/proc/self/fd/0",  # XXX: pip does not read requirements.txt from stdin
    ]
    subprocess.run(cmd, check=True, input=container_requirements_txt)

    if not os.listdir(args.dest):
        print(f">>> Failed to vendor PyMuPDF under '{args.dest}'", file=sys.stderr)

    print(f">>> Successfully vendored PyMuPDF under '{args.dest}'", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())

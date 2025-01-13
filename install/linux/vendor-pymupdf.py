#!/usr/bin/env python3

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

DZ_VENDOR_DIR = Path("./dangerzone/vendor")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dest",
        default=DZ_VENDOR_DIR,
        help="The destination directory for the vendored packages (default: ./dangerzone/vendor)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info("Getting PyMuPDF deps as requirements.txt")
    cmd = ["poetry", "export", "--only", "debian"]
    container_requirements_txt = subprocess.check_output(cmd)

    # XXX: Hack for Ubuntu Focal.
    #
    # The `requirements.txt` file is generated from our `pyproject.toml` file, and thus
    # specifies that the minimum Python version is 3.9. This was to accommodate to
    # PySide6, which is installed in macOS / Windows via `poetry` and works with Python
    # 3.9+. [1]
    #
    # The Python version in Ubuntu Focal though is 3.8. This generally was not much of
    # an issue, since we used the package manager to install dependencies. However, it
    # becomes an issue when we want to vendor the PyMuPDF package, using `pip`. In order
    # to sidestep this virtual limitation, we can just change the Python version in the
    # generated `requirements.txt` file in Ubuntu Focal from 3.9 to 3.8.
    #
    # [1] https://github.com/freedomofpress/dangerzone/pull/818
    if sys.version.startswith("3.8"):
        container_requirements_txt = container_requirements_txt.replace(b"3.9", b"3.8")

    logger.info(f"Vendoring PyMuPDF under '{args.dest}'")
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
        logger.error(f"Failed to vendor PyMuPDF under '{args.dest}'")

    logger.info(f"Successfully vendored PyMuPDF under '{args.dest}'")


if __name__ == "__main__":
    sys.exit(main())

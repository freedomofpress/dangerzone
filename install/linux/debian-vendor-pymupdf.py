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
    cmd = ["uv", "export", "--only-group", "debian"]
    container_requirements_txt = subprocess.check_output(cmd)

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

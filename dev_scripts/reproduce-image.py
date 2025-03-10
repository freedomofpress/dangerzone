#!/usr/bin/env python3

import argparse
import hashlib
import logging
import pathlib
import platform
import stat
import subprocess
import sys
import urllib.request

logger = logging.getLogger(__name__)

if platform.system() in ["Darwin", "Windows"]:
    CONTAINER_RUNTIME = "docker"
elif platform.system() == "Linux":
    CONTAINER_RUNTIME = "podman"


def run(*args):
    """Simple function that runs a command and checks the result."""
    logger.debug(f"Running command: {' '.join(args)}")
    return subprocess.run(args, check=True)


def build_image(
    platform=None,
    runtime=None,
    cache=True,
    date=None,
):
    """Build the Dangerzone container image with a special tag."""
    platform_args = [] if not platform else ["--platform", platform]
    runtime_args = [] if not runtime else ["--runtime", runtime]
    cache_args = [] if cache else ["--use-cache", "no"]
    date_args = [] if not date else ["--debian-archive-date", date]
    run(
        "python3",
        "./install/common/build-image.py",
        *platform_args,
        *runtime_args,
        *cache_args,
        *date_args,
    )


def parse_args():
    parser = argparse.ArgumentParser(
        prog=sys.argv[0],
        description="Dev script for verifying container image reproducibility",
    )
    parser.add_argument(
        "--platform",
        default=None,
        help=f"The platform for building the image (default: current platform)",
    )
    parser.add_argument(
        "--runtime",
        choices=["docker", "podman"],
        default=CONTAINER_RUNTIME,
        help=f"The container runtime for building the image (default: {CONTAINER_RUNTIME})",
    )
    parser.add_argument(
        "--no-cache",
        default=False,
        action="store_true",
        help=(
            "Do not use existing cached images for the container build."
            " Build from the start with a new set of cached layers."
        ),
    )
    parser.add_argument(
        "--debian-archive-date",
        default=None,
        help="Use a specific Debian snapshot archive, by its date",
    )
    parser.add_argument(
        "digest",
        help="The digest of the image that you want to reproduce",
    )
    return parser.parse_args()


def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    args = parse_args()

    logger.info(f"Building container image")
    build_image(
        args.platform,
        args.runtime,
        not args.no_cache,
        args.debian_archive_date,
    )

    logger.info(
        f"Check that the reproduced image has the expected digest: {args.digest}"
    )
    run(
        "./dev_scripts/repro-build.py",
        "analyze",
        "--show-contents",
        "share/container.tar",
        "--expected-image-digest",
        args.digest,
    )


if __name__ == "__main__":
    sys.exit(main())

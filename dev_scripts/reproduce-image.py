#!/usr/bin/env python3

import argparse
import hashlib
import logging
import pathlib
import stat
import subprocess
import sys
import urllib.request

logger = logging.getLogger(__name__)

DIFFOCI_URL = "https://github.com/reproducible-containers/diffoci/releases/download/v0.1.5/diffoci-v0.1.5.linux-amd64"
DIFFOCI_CHECKSUM = "01d25fe690196945a6bd510d30559338aa489c034d3a1b895a0d82a4b860698f"
DIFFOCI_PATH = (
    pathlib.Path.home() / ".local" / "share" / "dangerzone-dev" / "helpers" / "diffoci"
)
IMAGE_NAME = "dangerzone.rocks/dangerzone"


def run(*args):
    """Simple function that runs a command, validates it, and returns the output"""
    logger.debug(f"Running command: {" ".join(args)}")
    return subprocess.run(
        args,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def git_commit_get():
    return run("git", "rev-parse", "--short", "HEAD").decode().strip()


def git_determine_tag():
    return run("git", "describe", "--long", "--first-parent").decode().strip()


def git_verify(commit, source):
    if not commit in source:
        raise RuntimeError(
            f"Image '{source}' does not seem to be built from commit '{commit}'"
        )


def diffoci_hash_matches(diffoci):
    """Check if the hash of the downloaded diffoci bin matches the expected one."""
    m = hashlib.sha256()
    m.update(diffoci)
    diffoci_checksum = m.hexdigest()
    return diffoci_checksum == DIFFOCI_CHECKSUM


def diffoci_is_installed():
    """Determine if diffoci has been installed.

    Determine if diffoci has been installed, by checking if the binary exists, and if
    its hash is the expected one. If the binary exists but the hash is different, then
    this is a sign that we need to update the local diffoci binary.
    """
    if not DIFFOCI_PATH.exists():
        return False
    return diffoci_hash_matches(DIFFOCI_PATH.open("rb").read())


def diffoci_download():
    """Download the diffoci tool, based on a URL and its checksum."""
    with urllib.request.urlopen(DIFFOCI_URL) as f:
        diffoci_bin = f.read()

    if not diffoci_hash_matches(diffoci_bin):
        raise ValueError(
            "Unexpected checksum for downloaded diffoci binary:"
            f" {diffoci_checksum} !={DIFFOCI_CHECKSUM}"
        )

    DIFFOCI_PATH.parent.mkdir(parents=True, exist_ok=True)
    DIFFOCI_PATH.open("wb+").write(diffoci_bin)
    DIFFOCI_PATH.chmod(DIFFOCI_PATH.stat().st_mode | stat.S_IEXEC)


def diffoci_diff(source, local_target):
    """Diff the source image against the recently built target image using diffoci."""
    target = f"podman://{local_target}"
    try:
        return run(
            str(DIFFOCI_PATH),
            "diff",
            source,
            target,
            "--semantic",
            "--verbose",
        )
    except subprocess.CalledProcessError as e:
        error = e.stdout.decode()
        raise RuntimeError(
            f"Could not rebuild an identical image to {source}. Diffoci report:\n{error}"
        )


def build_image(tag, use_cache=False):
    """Build the Dangerzone container image with a special tag."""
    run(
        "python3",
        "./install/common/build-image.py",
        "--no-save",
        "--use-cache",
        str(use_cache),
        "--tag",
        tag,
    )


def parse_args():
    image_tag = git_determine_tag()
    # TODO: Remove the local "podman://" prefix once we have started pushing images to a
    # remote.
    default_image_name = "podman://" + IMAGE_NAME + ":" + image_tag

    parser = argparse.ArgumentParser(
        prog=sys.argv[0],
        description="Dev script for verifying container image reproducibility",
    )
    parser.add_argument(
        "--source",
        default=default_image_name,
        help=(
            "The name of the image that you want to reproduce. If the image resides in"
            " the local Docker / Podman engine, you can prefix it with podman:// or"
            f" docker:// accordingly (default: {default_image_name})"
        ),
    )
    parser.add_argument(
        "--use-cache",
        default=False,
        action="store_true",
        help="Whether to reuse the build cache (off by default for better reproducibility)",
    )
    return parser.parse_args()


def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    args = parse_args()

    logger.info(f"Ensuring that current Git commit matches image '{args.source}'")
    commit = git_commit_get()
    git_verify(commit, args.source)

    if not diffoci_is_installed():
        logger.info(f"Downloading diffoci helper from {DIFFOCI_URL}")
        diffoci_download()

    tag = f"reproduce-{commit}"
    target = f"dangerzone.rocks/dangerzone:{tag}"
    logger.info(f"Building container image and tagging it as '{target}'")
    build_image(tag, args.use_cache)

    logger.info(
        f"Ensuring that source image '{args.source}' is semantically identical with"
        f" built image '{target}'"
    )
    try:
        diffoci_diff(args.source, target)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Could not reproduce image {args.source} for commit {commit}"
        )
        breakpoint()

    logger.info(f"Successfully reproduced image '{args.source}' from commit '{commit}'")


if __name__ == "__main__":
    sys.exit(main())

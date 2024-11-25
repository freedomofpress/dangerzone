#!/usr/bin/env python3

import argparse
import hashlib
import logging
import pathlib
import subprocess
import sys

log = logging.getLogger(__name__)


DZ_ASSETS = [
    "container-{version}-i686.tar.gz",
    "container-{version}-arm64.tar.gz",
    "Dangerzone-{version}.msi",
    "Dangerzone-{version}-arm64.dmg",
    "Dangerzone-{version}-i686.dmg",
    "dangerzone-{version}.tar.gz",
]
DZ_SIGNING_PUBKEY = "DE28AB241FA48260FAC9B8BAA7C9B38522604281"


def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def sign_asset(asset, detached=True):
    """Sign a single Dangerzone asset using GPG.

    By default, ask GPG to create a detached signature. Alternatively, ask it to include
    the signature with the contents of the file.
    """
    _sign_opt = "--detach-sig" if detached else "--clearsign"
    cmd = [
        "gpg",
        "--batch",
        "--yes",
        "--armor",
        _sign_opt,
        "-u",
        DZ_SIGNING_PUBKEY,
        str(asset),
    ]
    log.info(f"Signing '{asset}'")
    log.debug(f"GPG command: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def hash_assets(assets):
    """Create a list of hashes for all the assets, mimicking the output of `sha256sum`.

    Compute the SHA-256 hash of every asset, and create a line for each asset that
    follows the format of `sha256sum`. From `man sha256sum`:

        The  sums  are  computed as described in FIPS-180-2.  When checking, the input
        should be a former output of this program.  The default mode is to print a
        line with: checksum, a space, a character indicating input mode ('*' for
        binary, ' ' for text or where binary is insignificant), and name for each
        FILE.
    """
    checksums = []
    for asset in assets:
        log.info(f"Hashing '{asset}'")
        with open(asset, "rb") as f:
            hexdigest = hashlib.file_digest(f, "sha256").hexdigest()
        checksums.append(f"{hexdigest}  {asset.name}")
    return "\n".join(checksums)


def ensure_assets_exist(assets):
    """Ensure that assets dir exists, and that the assets are all there."""
    dir = assets[0].parent
    if not dir.exists():
        raise ValueError(f"Path '{dir}' does not exist")
    if not dir.is_dir():
        raise ValueError(f"Path '{dir}' is not a directory")

    for asset in assets:
        if not asset.exists():
            raise ValueError(
                f"Expected asset with name '{asset}', but it does not exist"
            )


def main():
    parser = argparse.ArgumentParser(
        prog=sys.argv[0],
        description="Dev script for signing Dangerzone assets",
    )
    parser.add_argument(
        "--version",
        required=True,
        help="look for assets with this Dangerzone version",
    )
    parser.add_argument(
        "dir",
        help="look for assets in this directory",
    )
    args = parser.parse_args()
    setup_logging()

    # Ensure that all the necessary assets exist in the provided directory.
    log.info("> Ensuring that the required assets exist")
    dir = pathlib.Path(args.dir)
    assets = [dir / asset.format(version=args.version) for asset in DZ_ASSETS]
    ensure_assets_exist(assets)

    # Create a file that holds the SHA-256 hashes of the assets.
    log.info("> Create a checksums file for our assets")
    checksums = hash_assets(assets)
    checksums_file = dir / f"checksums-{args.version}.txt"
    with open(checksums_file, "w+") as f:
        f.write(checksums)

    # Sign every asset and create a detached signature (.asc) for each one of them. The
    # sole exception is the checksums file, which embeds its signature within the
    # file, and retains its original name.
    log.info("> Sign all of our assets")
    for asset in assets:
        sign_asset(asset)
    sign_asset(checksums_file, detached=False)
    (dir / f"checksums-{args.version}.txt.asc").rename(checksums_file)


if __name__ == "__main__":
    sys.exit(main())

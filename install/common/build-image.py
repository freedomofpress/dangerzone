import argparse
import platform
import secrets
import subprocess
import sys
from pathlib import Path

BUILD_CONTEXT = "dangerzone"
IMAGE_NAME = "ghcr.io/freedomofpress/dangerzone/dangerzone"
if platform.system() in ["Darwin", "Windows"]:
    CONTAINER_RUNTIME = "docker"
elif platform.system() == "Linux":
    CONTAINER_RUNTIME = "podman"


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")


def determine_git_tag():
    # Designate a unique tag for this image, depending on the Git commit it was created
    # from:
    # 1. If created from a Git tag (e.g., 0.8.0), the image tag will be `0.8.0`.
    # 2. If created from a commit, it will be something like `0.8.0-31-g6bdaa7a`.
    # 3. If the contents of the Git repo are dirty, we will append a unique identifier
    #    for this run, something like `0.8.0-31-g6bdaa7a-fdcb` or `0.8.0-fdcb`.
    dirty_ident = secrets.token_hex(2)
    return (
        subprocess.check_output(
            [
                "git",
                "describe",
                "--long",
                "--first-parent",
                f"--dirty=-{dirty_ident}",
            ],
        )
        .decode()
        .strip()[1:]  # remove the "v" prefix of the tag.
    )


def determine_debian_archive_date():
    """Get the date of the Debian archive from Dockerfile.env."""
    for env in Path("Dockerfile.env").read_text().split("\n"):
        if env.startswith("DEBIAN_ARCHIVE_DATE"):
            return env.split("=")[1]
    raise Exception(
        "Could not find 'DEBIAN_ARCHIVE_DATE' build argument in Dockerfile.env"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--runtime",
        choices=["docker", "podman"],
        default=CONTAINER_RUNTIME,
        help=f"The container runtime for building the image (default: {CONTAINER_RUNTIME})",
    )
    parser.add_argument(
        "--platform",
        default=None,
        help=f"The platform for building the image (default: current platform)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=str(Path("share") / "container.tar"),
        help="Path to store the container image",
    )
    parser.add_argument(
        "--use-cache",
        type=str2bool,
        nargs="?",
        default=True,
        const=True,
        help="Use the builder's cache to speed up the builds",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="Provide a custom tag for the image (for development only)",
    )
    parser.add_argument(
        "--debian-archive-date",
        "-d",
        default=determine_debian_archive_date(),
        help="Use a specific Debian snapshot archive, by its date (default %(default)s)",
    )
    parser.add_argument(
        "--dry",
        default=False,
        action="store_true",
        help="Do not run any commands, just print what would happen",
    )
    args = parser.parse_args()

    tag = args.tag or f"{args.debian_archive_date}-{determine_git_tag()}"
    image_name_tagged = f"{IMAGE_NAME}:{tag}"

    print(f"Will tag the container image as '{image_name_tagged}'")
    image_id_path = Path("share") / "image-id.txt"
    if not args.dry:
        with open(image_id_path, "w") as f:
            f.write(tag)

    # Build the container image, and tag it with the calculated tag
    print("Building container image")
    cache_args = [] if args.use_cache else ["--no-cache"]
    platform_args = [] if not args.platform else ["--platform", args.platform]
    rootless_args = [] if args.runtime == "docker" else ["--rootless"]
    rootless_args = []
    dry_args = [] if not args.dry else ["--dry"]

    subprocess.run(
        [
            sys.executable,
            str(Path("dev_scripts") / "repro-build.py"),
            "build",
            "--runtime",
            args.runtime,
            "--build-arg",
            f"DEBIAN_ARCHIVE_DATE={args.debian_archive_date}",
            "--datetime",
            args.debian_archive_date,
            *dry_args,
            *cache_args,
            *platform_args,
            *rootless_args,
            "--tag",
            image_name_tagged,
            "--output",
            args.output,
            "-f",
            "Dockerfile",
            BUILD_CONTEXT,
        ],
        check=True,
    )


if __name__ == "__main__":
    sys.exit(main())

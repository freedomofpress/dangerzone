import argparse
import gzip
import platform
import secrets
import subprocess
import sys
from pathlib import Path

BUILD_CONTEXT = "dangerzone/"
IMAGE_NAME = "dangerzone.rocks/dangerzone"
if platform.system() in ["Darwin", "Windows"]:
    CONTAINER_RUNTIME = "docker"
elif platform.system() == "Linux":
    CONTAINER_RUNTIME = "podman"

ARCH = platform.machine()


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--runtime",
        choices=["docker", "podman"],
        default=CONTAINER_RUNTIME,
        help=f"The container runtime for building the image (default: {CONTAINER_RUNTIME})",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save the container image as a tarball in share/container.tar.gz",
    )
    parser.add_argument(
        "--compress-level",
        type=int,
        choices=range(0, 10),
        default=9,
        help="The Gzip compression level, from 0 (lowest) to 9 (highest, default)",
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
    args = parser.parse_args()

    tarball_path = Path("share") / "container.tar.gz"
    image_id_path = Path("share") / "image-id.txt"

    print(f"Building for architecture '{ARCH}'")

    tag = args.tag or determine_git_tag()
    image_name_tagged = IMAGE_NAME + ":" + tag

    print(f"Will tag the container image as '{image_name_tagged}'")
    with open(image_id_path, "w") as f:
        f.write(tag)

    # Build the container image, and tag it with the calculated tag
    print("Building container image")
    cache_args = [] if args.use_cache else ["--no-cache"]
    subprocess.run(
        [
            args.runtime,
            "build",
            BUILD_CONTEXT,
            *cache_args,
            "-f",
            "Dockerfile",
            "--tag",
            image_name_tagged,
        ],
        check=True,
    )

    if not args.no_save:
        print("Saving container image")
        cmd = subprocess.Popen(
            [
                CONTAINER_RUNTIME,
                "save",
                image_name_tagged,
            ],
            stdout=subprocess.PIPE,
        )

        print("Compressing container image")
        chunk_size = 4 << 20
        with gzip.open(
            tarball_path,
            "wb",
            compresslevel=args.compress_level,
        ) as gzip_f:
            while True:
                chunk = cmd.stdout.read(chunk_size)
                if len(chunk) > 0:
                    gzip_f.write(chunk)
                else:
                    break
        cmd.wait(5)


if __name__ == "__main__":
    sys.exit(main())

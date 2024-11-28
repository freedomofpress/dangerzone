import argparse
import gzip
import os
import platform
import secrets
import subprocess
import sys
from pathlib import Path

BUILD_CONTEXT = "dangerzone/"
IMAGE_NAME = "dangerzone.rocks/dangerzone"
REQUIREMENTS_TXT = "container-pip-requirements.txt"
if platform.system() in ["Darwin", "Windows"]:
    CONTAINER_RUNTIME = "docker"
elif platform.system() == "Linux":
    CONTAINER_RUNTIME = "podman"

ARCH = platform.machine()

def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


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
        nargs='?',
        default=False,
        const=True,
        help="Use the builder's cache to speed up the builds (not suitable for release builds)",
    )
    parser.add_argument(
        "--force-tag",
        default=None,
        help="Force tag the image with this tag",
    )
    args = parser.parse_args()

    print(f"Building for architecture '{ARCH}'")
    dirty_tag = secrets.token_hex(2)

    if not args.force_tag:
        tag = subprocess.check_output(
            [
                "git",
                "describe",
                "--first-parent",
                f"--dirty=-{dirty_tag}"
            ],
        ).decode().strip()[1:]  # remove the "v" prefix of the tag.
    else:
        tag = args.force_tag
    image_name_tagged = IMAGE_NAME + ":" + tag

    print(f"Will tag the container image as '{image_name_tagged}'")

    print("Exporting container pip dependencies")
    with ContainerPipDependencies():
        if not args.use_cache:
            print("Pulling base image")
            subprocess.run(
                [
                    args.runtime,
                    "pull",
                    "alpine:latest",
                ],
                check=True,
            )

        print("Building container image")
        cache_args = [] if args.use_cache else ["--no-cache"]
        image_name_latest = IMAGE_NAME + ":latest"
        subprocess.run(
            [
                args.runtime,
                "build",
                BUILD_CONTEXT,
                *cache_args,
                "--build-arg",
                f"REQUIREMENTS_TXT={REQUIREMENTS_TXT}",
                "--build-arg",
                f"ARCH={ARCH}",
                "-f",
                "Dockerfile",
                "--tag",
                image_name_latest,
                "--tag",
                image_name_tagged,
            ],
            check=True,
        )

        print("Deleting previous container images")
        for f in Path("share").glob("container-*.tar.gz"):
            f.unlink()

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
                f"share/container-{tag}.tar.gz",
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


class ContainerPipDependencies:
    """Generates PIP dependencies within container"""

    def __enter__(self):
        try:
            container_requirements_txt = subprocess.check_output(
                ["poetry", "export", "--only", "container"], universal_newlines=True
            )
        except subprocess.CalledProcessError as e:
            print("FAILURE", e.returncode, e.output)
        print(f"REQUIREMENTS: {container_requirements_txt}")
        # XXX Export container dependencies and exclude pymupdfb since it is not needed in container
        req_txt_pymupdfb_stripped = container_requirements_txt.split("pymupdfb")[0]
        with open(Path(BUILD_CONTEXT) / REQUIREMENTS_TXT, "w") as f:
            if ARCH == "arm64":
                # PyMuPDF needs to be built on ARM64 machines
                # But is already provided as a prebuilt-wheel on other architectures
                f.write(req_txt_pymupdfb_stripped)
            else:
                f.write(container_requirements_txt)

    def __exit__(self, exc_type, exc_value, exc_tb):
        print("Leaving the context...")
        os.remove(Path(BUILD_CONTEXT) / REQUIREMENTS_TXT)


if __name__ == "__main__":
    sys.exit(main())

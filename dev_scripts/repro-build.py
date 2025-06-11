#!/usr/bin/env python3

import argparse
import datetime
import hashlib
import json
import logging
import os
import pprint
import shlex
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

logger = logging.getLogger(__name__)

MEDIA_TYPE_INDEX_V1_JSON = "application/vnd.oci.image.index.v1+json"
MEDIA_TYPE_MANIFEST_V1_JSON = "application/vnd.oci.image.manifest.v1+json"

ENV_RUNTIME = "REPRO_RUNTIME"
ENV_DATETIME = "REPRO_DATETIME"
ENV_SDE = "REPRO_SOURCE_DATE_EPOCH"
ENV_CACHE = "REPRO_CACHE"
ENV_BUILDKIT = "REPRO_BUILDKIT_IMAGE"
ENV_ROOTLESS = "REPRO_ROOTLESS"

DEFAULT_BUILDKIT_IMAGE = "moby/buildkit:v0.19.0@sha256:14aa1b4dd92ea0a4cd03a54d0c6079046ea98cd0c0ae6176bdd7036ba370cbbe"
DEFAULT_BUILDKIT_IMAGE_ROOTLESS = "moby/buildkit:v0.19.0-rootless@sha256:e901cffdad753892a7c3afb8b9972549fca02c73888cf340c91ed801fdd96d71"

MSG_BUILD_CTX = """Build environment:
- Container runtime: {runtime}
- BuildKit image: {buildkit_image}
- Rootless support: {rootless}
- Caching enabled: {use_cache}
- Build context: {context}
- Dockerfile: {dockerfile}
- Output: {output}

Build parameters:
- SOURCE_DATE_EPOCH: {sde}
- Build args: {build_args}
- Tag: {tag}
- Platform: {platform}

Podman-only arguments:
- BuildKit arguments: {buildkit_args}

Docker-only arguments:
- Docker Buildx arguments: {buildx_args}
"""


def pretty_error(obj: dict, msg: str):
    raise Exception(f"{msg}\n{pprint.pprint(obj)}")


def get_key(obj: dict, key: str) -> object:
    if key not in obj:
        pretty_error(f"Could not find key '{key}' in the dictionary:", obj)
    return obj[key]


def run(cmd, dry=False, check=True):
    action = "Would have run" if dry else "Running"
    logger.debug(f"{action}: {shlex.join(cmd)}")
    if not dry:
        subprocess.run(cmd, check=check)


def snip_contents(contents: str, num: int) -> str:
    contents = contents.replace("\n", "")
    if len(contents) > num:
        return (
            contents[:num]
            + f"  [... {len(contents) - num} characters omitted."
            + " Pass --show-contents to print them in their entirety]"
        )
    return contents


def detect_container_runtime() -> str:
    """Auto-detect the installed container runtime in the system."""
    if shutil.which("docker"):
        return "docker"
    elif shutil.which("podman"):
        return "podman"
    else:
        return None


def parse_runtime(args) -> str:
    if args.runtime is not None:
        return args.runtime

    runtime = os.environ.get(ENV_RUNTIME)
    if runtime is None:
        raise RuntimeError("No container runtime detected in your system")
    if runtime not in ("docker", "podman"):
        raise RuntimeError(
            "Only 'docker' or 'podman' container runtimes"
            " are currently supported by this script"
        )


def parse_use_cache(args) -> bool:
    if args.no_cache:
        return False
    return bool(int(os.environ.get(ENV_CACHE, "1")))


def parse_rootless(args, runtime: str) -> bool:
    rootless = args.rootless or bool(int(os.environ.get(ENV_ROOTLESS, "0")))
    if runtime != "podman" and rootless:
        raise RuntimeError("Rootless mode is only supported with Podman runtime")
    return rootless


def parse_sde(args) -> str:
    sde = os.environ.get(ENV_SDE, args.source_date_epoch)
    dt = os.environ.get(ENV_DATETIME, args.datetime)

    if (sde is not None and dt is not None) or (sde is None and dt is None):
        raise RuntimeError("You need to pass either a source date epoch or a datetime")

    if sde is not None:
        return str(sde)

    if dt is not None:
        d = datetime.datetime.fromisoformat(dt)
        # If the datetime is naive, assume its timezone is UTC. The check is
        # taken from:
        # https://docs.python.org/3/library/datetime.html#determining-if-an-object-is-aware-or-naive
        if d.tzinfo is None or d.tzinfo.utcoffset(d) is None:
            d = d.replace(tzinfo=datetime.timezone.utc)
        return int(d.timestamp())


def parse_buildkit_image(args, rootless: bool, runtime: str) -> str:
    default = DEFAULT_BUILDKIT_IMAGE_ROOTLESS if rootless else DEFAULT_BUILDKIT_IMAGE
    img = args.buildkit_image or os.environ.get(ENV_BUILDKIT, default)

    if runtime == "podman" and not img.startswith("docker.io/"):
        img = "docker.io/" + img

    return img


def parse_build_args(args) -> str:
    return args.build_arg or []


def parse_buildkit_args(args, runtime: str) -> str:
    if not args.buildkit_args:
        return []

    if runtime != "podman":
        raise RuntimeError("Cannot specify BuildKit arguments using the Docker runtime")

    return shlex.split(args.buildkit_args)


def parse_buildx_args(args, runtime: str) -> str:
    if not args.buildx_args:
        return []

    if runtime != "docker":
        raise RuntimeError(
            "Cannot specify Docker Buildx arguments using the Podman runtime"
        )

    return shlex.split(args.buildx_args)


def parse_image_digest(args) -> str | None:
    if not args.expected_image_digest:
        return None
    parsed = args.expected_image_digest.split(":", 1)
    if len(parsed) == 1:
        return parsed[0]
    else:
        return parsed[1]


def parse_path(path: str | None) -> str | None:
    return path and str(Path(path).absolute())


##########################
# OCI parsing logic
#
# Compatible with:
# * https://github.com/opencontainers/image-spec/blob/main/image-layout.md


def oci_print_info(parsed: dict, full: bool) -> None:
    print(f"The OCI tarball contains an index and {len(parsed) - 1} manifest(s):")
    print()
    print(f"Image digest: {parsed[1]['digest']}")
    for i, info in enumerate(parsed):
        print()
        if i == 0:
            print(f"Index ({info['path']}):")
        else:
            print(f"Manifest {i} ({info['path']}):")
        print(f"  Digest: {info['digest']}")
        print(f"  Media type: {info['media_type']}")
        print(f"  Platform: {info['platform'] or '-'}")
        contents = info["contents"] if full else snip_contents(info["contents"], 600)
        print(f"  Contents: {contents}")
    print()


def oci_normalize_path(path):
    if path.startswith("sha256:"):
        hash_algo, checksum = path.split(":")
        path = f"blobs/{hash_algo}/{checksum}"
    return path


def oci_get_file_from_tarball(tar: tarfile.TarFile, path: str) -> dict:
    """Get file from an OCI tarball.

    If the filename cannot be found, search again by prefixing it with "./", since we
    have encountered path names in OCI tarballs prefixed with "./".
    """
    try:
        return tar.extractfile(path).read().decode()
    except KeyError:
        if not path.startswith("./") and not path.startswith("/"):
            path = "./" + path
            try:
                return tar.extractfile(path).read().decode()
            except KeyError:
                # Do not raise here, so that we can raise the original exception below.
                pass
        raise


def oci_parse_manifest(tar: tarfile.TarFile, path: str, platform: dict | None) -> dict:
    """Parse manifest information in JSON format.

    Interestingly, the platform info for a manifest is not included in the
    manifest itself, but in the descriptor that points to it. So, we have to
    carry it from the previous manifest and include in the info here.
    """
    path = oci_normalize_path(path)
    contents = oci_get_file_from_tarball(tar, path)
    digest = "sha256:" + hashlib.sha256(contents.encode()).hexdigest()
    contents_dict = json.loads(contents)
    media_type = get_key(contents_dict, "mediaType")
    manifests = contents_dict.get("manifests", [])

    if platform:
        os = get_key(platform, "os")
        arch = get_key(platform, "architecture")
        platform = f"{os}/{arch}"

    return {
        "path": path,
        "contents": contents,
        "digest": digest,
        "media_type": media_type,
        "platform": platform,
        "manifests": manifests,
    }


def oci_parse_manifests_dfs(
    tar: tarfile.TarFile, path: str, parsed: list, platform: dict | None = None
) -> None:
    info = oci_parse_manifest(tar, path, platform)
    parsed.append(info)
    for m in info["manifests"]:
        oci_parse_manifests_dfs(tar, m["digest"], parsed, m.get("platform"))


def oci_parse_tarball(path: Path) -> dict:
    parsed = []
    with tarfile.TarFile.open(path) as tar:
        oci_parse_manifests_dfs(tar, "index.json", parsed)
    return parsed


##########################
# Image building logic


def podman_build(
    context: str,
    dockerfile: str | None,
    tag: str | None,
    buildkit_image: str,
    sde: int,
    rootless: bool,
    use_cache: bool,
    output: Path,
    build_args: list,
    platform: str,
    buildkit_args: list,
    dry: bool,
):
    rootless_args = []
    rootful_args = []
    if rootless:
        rootless_args = [
            "--userns",
            "keep-id:uid=1000,gid=1000",
            "--security-opt",
            "seccomp=unconfined",
            "--security-opt",
            "apparmor=unconfined",
            "-e",
            "BUILDKITD_FLAGS=--oci-worker-no-process-sandbox",
        ]
    else:
        rootful_args = ["--privileged"]

    dockerfile_args_podman = []
    dockerfile_args_buildkit = []
    if dockerfile:
        dockerfile_args_podman = ["-v", f"{dockerfile}:/tmp/Dockerfile"]
        dockerfile_args_buildkit = ["--local", "dockerfile=/tmp"]
    else:
        dockerfile_args_buildkit = ["--local", "dockerfile=/tmp/work"]

    tag_args = f",name={tag}" if tag else ""

    cache_args = []
    if use_cache:
        cache_args = [
            "--export-cache",
            "type=local,mode=max,dest=/tmp/cache",
            "--import-cache",
            "type=local,src=/tmp/cache",
        ]

    _build_args = []
    for arg in build_args:
        _build_args.append("--opt")
        _build_args.append(f"build-arg:{arg}")
    platform_args = ["--opt", f"platform={platform}"] if platform else []

    cmd = [
        "podman",
        "run",
        "-it",
        "--rm",
        "-v",
        "buildkit_cache:/tmp/cache",
        "-v",
        f"{output.parent}:/tmp/image",
        "-v",
        f"{context}:/tmp/work",
        "--entrypoint",
        "buildctl-daemonless.sh",
        *rootless_args,
        *rootful_args,
        *dockerfile_args_podman,
        buildkit_image,
        "build",
        "--frontend",
        "dockerfile.v0",
        "--local",
        "context=/tmp/work",
        "--opt",
        f"build-arg:SOURCE_DATE_EPOCH={sde}",
        *_build_args,
        "--output",
        f"type=docker,dest=/tmp/image/{output.name},rewrite-timestamp=true{tag_args}",
        *cache_args,
        *dockerfile_args_buildkit,
        *platform_args,
        *buildkit_args,
    ]

    run(cmd, dry)


def docker_build(
    context: str,
    dockerfile: str | None,
    tag: str | None,
    buildkit_image: str,
    sde: int,
    use_cache: bool,
    output: Path,
    build_args: list,
    platform: str,
    buildx_args: list,
    dry: bool,
):
    builder_id = hashlib.sha256(buildkit_image.encode()).hexdigest()
    builder_name = f"repro-build-{builder_id}"
    tag_args = ["-t", tag] if tag else []
    cache_args = [] if use_cache else ["--no-cache", "--pull"]

    cmd = [
        "docker",
        "buildx",
        "create",
        "--name",
        builder_name,
        "--driver-opt",
        f"image={buildkit_image}",
    ]
    run(cmd, dry, check=False)

    dockerfile_args = ["-f", dockerfile] if dockerfile else []
    _build_args = []
    for arg in build_args:
        _build_args.append("--build-arg")
        _build_args.append(arg)
    platform_args = ["--platform", platform] if platform else []

    cmd = [
        "docker",
        "buildx",
        "--builder",
        builder_name,
        "build",
        "--build-arg",
        f"SOURCE_DATE_EPOCH={sde}",
        *_build_args,
        "--provenance",
        "false",
        "--output",
        f"type=docker,dest={output},rewrite-timestamp=true",
        *cache_args,
        *tag_args,
        *dockerfile_args,
        *platform_args,
        *buildx_args,
        context,
    ]
    run(cmd, dry)


##########################
# Command logic


def build(args):
    runtime = parse_runtime(args)
    use_cache = parse_use_cache(args)
    sde = parse_sde(args)
    rootless = parse_rootless(args, runtime)
    buildkit_image = parse_buildkit_image(args, rootless, runtime)
    build_args = parse_build_args(args)
    platform = args.platform
    buildkit_args = parse_buildkit_args(args, runtime)
    buildx_args = parse_buildx_args(args, runtime)
    tag = args.tag
    dockerfile = parse_path(args.file)
    output = Path(parse_path(args.output))
    dry = args.dry
    context = parse_path(args.context)

    logger.info(
        MSG_BUILD_CTX.format(
            runtime=runtime,
            buildkit_image=buildkit_image,
            sde=sde,
            rootless=rootless,
            use_cache=use_cache,
            context=context,
            dockerfile=dockerfile or "(not provided)",
            tag=tag or "(not provided)",
            output=output,
            build_args=",".join(build_args) or "(not provided)",
            platform=platform or "(default)",
            buildkit_args=" ".join(buildkit_args) or "(not provided)",
            buildx_args=" ".join(buildx_args) or "(not provided)",
        )
    )

    try:
        if runtime == "docker":
            docker_build(
                context,
                dockerfile,
                tag,
                buildkit_image,
                sde,
                use_cache,
                output,
                build_args,
                platform,
                buildx_args,
                dry,
            )
        else:
            podman_build(
                context,
                dockerfile,
                tag,
                buildkit_image,
                sde,
                rootless,
                use_cache,
                output,
                build_args,
                platform,
                buildkit_args,
                dry,
            )
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed with {e.returncode}")
        sys.exit(e.returncode)


def analyze(args) -> None:
    expected_image_digest = parse_image_digest(args)
    tarball_path = Path(args.tarball)

    parsed = oci_parse_tarball(tarball_path)
    oci_print_info(parsed, args.show_contents)

    if expected_image_digest:
        cur_digest = parsed[1]["digest"].split(":")[1]
        if cur_digest != expected_image_digest:
            raise Exception(
                f"The image does not have the expected digest: {cur_digest} != {expected_image_digest}"
            )
        print(f"✅ Image digest matches {expected_image_digest}")


def define_build_cmd_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--runtime",
        choices=["docker", "podman"],
        default=detect_container_runtime(),
        help="The container runtime for building the image (default: %(default)s)",
    )
    parser.add_argument(
        "--datetime",
        metavar="YYYY-MM-DD",
        default=None,
        help=(
            "Provide a date and (optionally) a time in ISO format, which will"
            " be used as the timestamp of the image layers"
        ),
    )
    parser.add_argument(
        "--buildkit-image",
        metavar="NAME:TAG@DIGEST",
        default=None,
        help=(
            "The BuildKit container image which will be used for building the"
            " reproducible container image. Make sure to pass the '-rootless'"
            " variant if you are using rootless Podman"
            " (default: docker.io/moby/buildkit:v0.19.0)"
        ),
    )
    parser.add_argument(
        "--source-date-epoch",
        "--sde",
        metavar="SECONDS",
        type=int,
        default=None,
        help="Provide a Unix timestamp for the image layers",
    )
    parser.add_argument(
        "--no-cache",
        default=False,
        action="store_true",
        help="Do not use existing cached images for the container build. Build from the start with a new set of cached layers.",
    )
    parser.add_argument(
        "--rootless",
        default=False,
        action="store_true",
        help="Run BuildKit in rootless mode (Podman only)",
    )
    parser.add_argument(
        "-f",
        "--file",
        metavar="FILE",
        default=None,
        help="Pathname of a Dockerfile",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        default=Path.cwd() / "image.tar",
        help="Path to save OCI tarball (default: %(default)s)",
    )
    parser.add_argument(
        "-t",
        "--tag",
        metavar="TAG",
        default=None,
        help="Tag the built image with the name %(metavar)s",
    )
    parser.add_argument(
        "--build-arg",
        metavar="ARG=VALUE",
        action="append",
        default=None,
        help="Set build-time variables",
    )
    parser.add_argument(
        "--platform",
        metavar="PLAT1,PLAT2",
        default=None,
        help="Set platform for the image",
    )
    parser.add_argument(
        "--buildkit-args",
        metavar="'ARG1 ARG2'",
        default=None,
        help="Extra arguments for BuildKit (Podman only)",
    )
    parser.add_argument(
        "--buildx-args",
        metavar="'ARG1 ARG2'",
        default=None,
        help="Extra arguments for Docker Buildx (Docker only)",
    )
    parser.add_argument(
        "--dry",
        default=False,
        action="store_true",
        help="Do not run any commands, just print what would happen",
    )
    parser.add_argument(
        "context",
        metavar="CONTEXT",
        help="Path to the build context",
    )


def parse_args() -> dict:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    build_parser = subparsers.add_parser("build", help="Perform a build operation")
    build_parser.set_defaults(func=build)
    define_build_cmd_args(build_parser)

    analyze_parser = subparsers.add_parser("analyze", help="Analyze an OCI tarball")
    analyze_parser.set_defaults(func=analyze)
    analyze_parser.add_argument(
        "tarball",
        metavar="FILE",
        help="Path to OCI image in .tar format",
    )
    analyze_parser.add_argument(
        "--expected-image-digest",
        metavar="DIGEST",
        default=None,
        help="The expected digest for the provided image",
    )
    analyze_parser.add_argument(
        "--show-contents",
        default=False,
        action="store_true",
        help="Show full file contents",
    )

    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    args = parse_args()

    if not hasattr(args, "func"):
        args.func = build
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())

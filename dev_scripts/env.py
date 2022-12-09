#!/usr/bin/env python3

import argparse
import os
import pathlib
import shutil
import subprocess
import sys

DEFAULT_GUI = False
DEFAULT_USER = "user"
DEFAULT_DRY = False
DEFAULT_DEV = False
DEFAULT_SHOW_DOCKERFILE = False

# The Linux distributions that we currently support.
# FIXME: Add a version mapping to avoid mistakes.
# FIXME: Maybe create an enum for these values.
DISTROS = ["debian", "fedora", "ubuntu"]
CONTAINER_RUNTIMES = ["podman", "docker"]
IMAGE_NAME_BUILD_DEV_FMT = "dangerzone.rocks/build/{distro}:{version}"
IMAGE_NAME_BUILD_FMT = "dangerzone.rocks/{distro}:{version}"

EPILOG = """\
Examples:

Build a Dangerzone environment for development (build-dev) or testing (build) based on
Ubuntu 22.04:

    env.py --distro ubuntu --version 22.04 build-dev
    env.py --distro ubuntu --version 22.04 build

Inspect the Dockerfile for the environments:

    env.py --distro ubuntu --version 22.04 build-dev --show-dockerfile
    env.py --distro ubuntu --version 22.04 build --show-dockerfile

Run an interactive shell in the development or end-user environment:

    env.py --distro ubuntu --version 22.04 run --dev bash
    env.py --distro ubuntu --version 22.04 run bash

Run Dangerzone in the development environment:

    env.py --distro ubuntu --version 22.04 run --dev --gui bash
    user@dangerzone-dev:~$ cd dangerzone/
    user@dangerzone-dev:~$ poetry run ./dev/scripts/dangerzone

Run Dangerzone in the end-user environment:

    env.py --distro ubuntu --version 22.04 run --gui dangerzone

"""

DOCKERFILE_BUILD_DEV_DEBIAN_DEPS = rf"""
RUN apt-get update && apt-get install -y \
    podman dh-python python3 python3-stdeb python3-pyside2.qtcore \
    python3-pyside2.qtgui python3-pyside2.qtwidgets python3-appdirs \
    python3-click python3-xdg python3-colorama

RUN apt-get update && apt-get install -y make
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3-dev python3-venv python3-pip
"""

# FIXME: Install Poetry on Fedora via package manager.
DOCKERFILE_BUILD_DEV_FEDORA_DEPS = r"""
RUN dnf update -y && dnf install -y rpm-build podman python3 python3-setuptools \
    python3-pyside2 python3-appdirs python3-click python3-pyxdg python3-colorama
RUN dnf update -y && dnf install -y make
RUN dnf update -y && dnf install -y python3-pip

# FIXME: Drop this fix after it's resolved upstream.
# See https://github.com/freedomofpress/dangerzone/issues/286#issuecomment-1347149783
RUN dnf reinstall -y shadow-utils && dnf clean all

RUN dnf install -y mupdf && dnf clean all
"""

# The Dockerfile for building a development environment for Dangerzone. Parts of the
# Dockerfile will be populated during runtime.
DOCKERFILE_BUILD_DEV = r"""FROM {distro}:{version}

{install_deps}

RUN python3 -m pip install poetry

#########################################
# Create a non-root user to run Dangerzone
RUN adduser user
# See https://github.com/freedomofpress/dangerzone/issues/286#issuecomment-1347149783
RUN echo user:2000:2000 > /etc/subuid
RUN echo user:2000:2000 > /etc/subgid

# XXX: We need the empty source folder, so that we can trick Poetry to create a
# link to the project's path. This way, we should be able to do `import
# dangerzone` from within the container.
RUN mkdir -p /home/user/dangerzone/dangerzone
RUN touch /home/user/dangerzone/dangerzone/__init__.py

USER user
WORKDIR /home/user
VOLUME /home/user/dangerzone

COPY pyproject.toml poetry.lock /home/user/dangerzone/
RUN cd /home/user/dangerzone && poetry install
"""

DOCKERFILE_BUILD_DEBIAN_DEPS = r"""
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends mupdf \
    && rm -rf /var/lib/apt/lists/*
"""

DOCKERFILE_BUILD_FEDORA_DEPS = r"""
RUN dnf install -y mupdf && dnf clean all

# FIXME: Drop this fix after it's resolved upstream.
# See https://github.com/freedomofpress/dangerzone/issues/286#issuecomment-1347149783
RUN dnf reinstall -y shadow-utils && dnf clean all
"""

# The Dockerfile for building an environment with Dangerzone installed in it. Parts of
# the Dockerfile will be populated during runtime.
#
# FIXME: The fact that we remove the package does not reduce the image size. We need to
# flatten the image layers as well.
DOCKERFILE_BUILD = r"""FROM {distro}:{version}

{install_deps}

COPY {package} /tmp/{package}
RUN {install_cmd} /tmp/{package}
RUN rm /tmp/{package}

#########################################
# Create a non-root user to run Dangerzone
RUN adduser user
# See https://github.com/freedomofpress/dangerzone/issues/286#issuecomment-1347149783
RUN echo user:2000:2000 > /etc/subuid
RUN echo user:2000:2000 > /etc/subgid

USER user
WORKDIR /home/user
"""


def run(*args):
    """Simple function that runs a command, validates it, and returns the output"""
    return subprocess.run(
        args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ).stdout


def git_root():
    """Get the root directory of the Git repo."""
    # FIXME: Use a Git Python binding for this.
    # FIXME: Make this work if called outside the repo.
    path = run("git", "rev-parse", "--show-toplevel").decode().strip("\n")
    return pathlib.Path(path)


def distro_root(distro, version):
    """Get the root directory for the specific Linux environment."""
    return git_root() / f"dev_scripts/envs/{distro}/{version}"


def distro_state(distro, version):
    """Get the directory where we will store the state for the distro."""
    return distro_root(distro, version) / "state"


def distro_build(distro, version):
    """Get the directory where we will store the build files for the distro."""
    return distro_root(distro, version) / "build"


def image_name_build(distro, version):
    """Get the container image for the dev variant of a Dangerzone environment."""
    return IMAGE_NAME_BUILD_DEV_FMT.format(distro=distro, version=version)


def image_name_install(distro, version):
    """Get the container image for the Dangerzone environment."""
    return IMAGE_NAME_BUILD_FMT.format(distro=distro, version=version)


def dz_version():
    """Get the current Dangerzone version."""
    with open(git_root() / "share/version.txt") as f:
        return f.read().strip()


class Env:
    """A class that implements actions on Dangerzone environments"""

    def __init__(self, distro, version, runtime):
        """Initialize an Env class based on some common parameters."""
        self.distro = distro
        self.version = version

        # Try to autodetect the runtime, if the user has not provided it.
        #
        # FIXME: Typically Podman runs without sudo, whereas Docker with sudo, but this
        # is not always the case. We may need to autodetect that as well.
        podman_cmd = ["podman"]
        docker_cmd = ["sudo", "docker"]
        if not runtime:
            if shutil.which("podman"):
                self.runtime = "podman"
                self.runtime_cmd = podman_cmd
            elif shutil.which("docker"):
                self.runtime = "docker"
                self.runtime_cmd = docker_cmd
            else:
                raise SystemError(
                    "You need either Podman or Docker installed to continue"
                )
        elif runtime == "podman":
            self.runtime = "podman"
            self.runtime_cmd = podman_cmd
        elif runtime == "docker":
            self.runtime = "docker"
            self.runtime_cmd = docker_cmd
        else:
            raise RuntimeError(f"Unexpected runtime: {runtime}")

    @classmethod
    def from_args(cls, args):
        """Create an Env class from CLI arguments"""
        return cls(distro=args.distro, version=args.version, runtime=args.runtime)

    def runtime_run(self, *args):
        """Run a command for a specific container runtime.

        A user's environment may have more than one container runtime [1], e.g., Podman
        or Docker. These two runtimes have the same interface, so we can use them
        interchangeably.

        This method expects a command to run, minus the "docker" / "podman" part. Since
        the command can be any valid command, such as "run" or "build", we can't assume
        anything about the standard streams, so we don't affect them at all.

        [1]: Technically, a container runtime is a program that implements the Container
        Runtime Interface. We overload this term here, in lieu of a better one.
        """
        subprocess.run(self.runtime_cmd + list(args), check=True)

    def run(
        self, cmd, gui=DEFAULT_GUI, user=DEFAULT_USER, dry=DEFAULT_DRY, dev=DEFAULT_DEV
    ):
        """Run a command in a Dangerzone environment."""
        # FIXME: Allow wiping the state of the distro before running the environment, to
        # ensure reproducibility.

        run_cmd = [
            "run",
            "--rm",
            "-it",
            "-v",
            "/etc/localtime:/etc/localtime:ro",
            # FIXME: Find a more secure invocation.
            "--security-opt",
            "seccomp=unconfined",
            "--privileged",
        ]

        # We need to retain our UID, because we are mounting the Dangerzone source to
        # the container.
        if self.runtime == "podman":
            run_cmd += ["--userns", "keep-id"]

        # Compute container runtime arguments for GUI purposes.
        if gui:
            # Detect X11 display server connection settings.
            env_display = os.environ.get("DISPLAY")
            env_xauthority = os.environ.get("XAUTHORITY")
            run_cmd += [
                "-e",
                f"DISPLAY={env_display}",
                "-v",
                "/tmp/.X11-unix:/tmp/.X11-unix:ro",
            ]

            if env_xauthority:
                run_cmd += [
                    "-e",
                    f"XAUTHORITY={env_xauthority}",
                    "-v",
                    f"{env_xauthority}:{env_xauthority}:ro",
                ]

            # FIXME: Detect Wayland connection settings. This requires some extra
            # settings, as we can see in this link:
            #
            # https://github.com/mviereck/x11docker/wiki/How-to-provide-Wayland-socket-to-docker-container

        # Mount the source and the state of the distro into the container
        dz_src = git_root()
        dist_state = distro_state(self.distro, self.version)
        run_cmd += [
            "-v",
            f"{dz_src}:/home/user/dangerzone",
            "-v",
            f"{dist_state}/containers:/home/user/.local/share/containers",
            "-v",
            f"{dist_state}/.bash_history:/home/user/.bash_history",
        ]

        run_cmd += ["-u", user]

        # Select the proper container image based on whether the user wants to run the
        # command in a dev or end-user environment.
        if dev:
            run_cmd += [
                "--hostname",
                "dangerzone-dev",
                image_name_build(self.distro, self.version),
            ]
        else:
            run_cmd += [
                "--hostname",
                "dangerzone",
                image_name_install(self.distro, self.version),
            ]

        run_cmd += cmd

        # If the user has asked to perform a dry-run, then print the command that the
        # script would use internally.
        if dry:
            print(" ".join(self.runtime_cmd + list(run_cmd)))
            return

        dist_state.mkdir(exist_ok=True)
        (dist_state / "containers").mkdir(exist_ok=True)
        (dist_state / ".bash_history").touch(exist_ok=True)
        self.runtime_run(*run_cmd)

    def build_dev(self, show_dockerfile=DEFAULT_SHOW_DOCKERFILE):
        """Build a Linux environment and install tools for Dangerzone development."""
        if self.distro == "fedora":
            install_deps = DOCKERFILE_BUILD_DEV_FEDORA_DEPS
        else:
            install_deps = DOCKERFILE_BUILD_DEV_DEBIAN_DEPS

        dockerfile = DOCKERFILE_BUILD_DEV.format(
            distro=self.distro, version=self.version, install_deps=install_deps
        )
        if show_dockerfile:
            print(dockerfile)
            return

        build_dir = distro_build(self.distro, self.version)
        os.makedirs(build_dir, exist_ok=True)

        # Populate the build context.
        shutil.copy(git_root() / "pyproject.toml", build_dir)
        shutil.copy(git_root() / "poetry.lock", build_dir)
        with open(build_dir / "Dockerfile", mode="w") as f:
            f.write(dockerfile)

        image = image_name_build(self.distro, self.version)
        self.runtime_run("build", "-t", image, build_dir)

    def build(self, show_dockerfile=DEFAULT_SHOW_DOCKERFILE):
        """Build a Linux environment and install Dangerzone in it."""
        build_dir = distro_build(self.distro, self.version)
        version = dz_version()
        if self.distro == "fedora":
            install_deps = DOCKERFILE_BUILD_FEDORA_DEPS
            package = f"dangerzone-{version}-1.noarch.rpm"
            package_src = git_root() / "dist" / package
            package_dst = build_dir / package
            install_cmd = "dnf install -y"
        else:
            install_deps = DOCKERFILE_BUILD_DEBIAN_DEPS
            package = f"dangerzone_{version}-1_all.deb"
            package_src = git_root() / "deb_dist" / package
            package_dst = build_dir / package
            install_cmd = "apt-get update && apt-get install -y"

        dockerfile = DOCKERFILE_BUILD.format(
            distro=self.distro,
            version=self.version,
            install_cmd=install_cmd,
            package=package,
            install_deps=install_deps,
        )
        if show_dockerfile:
            print(dockerfile)
            return

        os.makedirs(build_dir, exist_ok=True)

        # Populate the build context.
        shutil.copy(package_src, package_dst)
        with open(build_dir / "Dockerfile", mode="w") as f:
            f.write(dockerfile)

        image = image_name_install(self.distro, self.version)
        self.runtime_run("build", "-t", image, build_dir)


def env_run(args):
    """Invoke the 'run' command based on the CLI args."""
    if not args.command:
        print("Please provide a command for the environment")
        sys.exit(1)

    env = Env.from_args(args)
    env.run(args.command, gui=args.gui, user=args.user, dry=args.dry, dev=args.dev)


def env_build_dev(args):
    """Invoke the 'build-dev' command based on the CLI args."""
    env = Env.from_args(args)
    env.build_dev(show_dockerfile=args.show_dockerfile)


def env_build(args):
    """Invoke the 'build' command based on the CLI args."""
    env = Env.from_args(args)
    env.build(show_dockerfile=args.show_dockerfile)


def parse_args():
    parser = argparse.ArgumentParser(
        prog=sys.argv[0],
        description="Dev script for handling Dangerzone environments",
        epilog=EPILOG,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--distro",
        choices=DISTROS,
        required=True,
        help="The name of the Linux distro",
    )
    parser.add_argument(
        "--version",
        required=True,
        help="The version of the Linux distro",
    )
    parser.add_argument(
        "--runtime",
        choices=CONTAINER_RUNTIMES,
        help="The name of the container runtime",
    )
    subparsers = parser.add_subparsers(help="Available subcommands")
    subparsers.required = True

    # Run a command in an environment.
    parser_run = subparsers.add_parser(
        "run", help="Run a command in a Dangerzone environment"
    )
    parser_run.set_defaults(func=env_run)
    parser_run.add_argument(
        "-g",
        "--gui",
        default=DEFAULT_GUI,
        action="store_true",
        help="Run command with GUI support",
    )
    parser_run.add_argument(
        "--user",
        "-u",
        default=DEFAULT_USER,
        help="Run command as user USER",
    )
    parser_run.add_argument(
        "--dry",
        default=DEFAULT_DRY,
        action="store_true",
        help="Do not run the command, just print it with the container invocation",
    )
    parser_run.add_argument(
        "--dev",
        default=DEFAULT_DEV,
        action="store_true",
        help="Run the command into the dev variant of the Dangerzone environment",
    )
    parser_run.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Run command COMMAND in the Dangerzone environment",
    )

    # Build a development variant of a Dangerzone environment.
    parser_build_dev = subparsers.add_parser(
        "build-dev",
        help="Build a Linux environment and install tools for Dangerzone development",
    )
    parser_build_dev.set_defaults(func=env_build_dev)
    parser_build_dev.add_argument(
        "--show-dockerfile",
        default=DEFAULT_SHOW_DOCKERFILE,
        action="store_true",
        help="Do not build, only show the Dockerfile",
    )

    # Build a development variant of a Dangerzone environment.
    parser_build = subparsers.add_parser(
        "build",
        help="Build a Linux environment and install Dangerzone",
    )
    parser_build.set_defaults(func=env_build)
    parser_build.add_argument(
        "--show-dockerfile",
        default=DEFAULT_SHOW_DOCKERFILE,
        action="store_true",
        help="Do not build, only show the Dockerfile",
    )

    return parser.parse_args()


def main():
    args = parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

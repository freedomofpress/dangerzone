#!/usr/bin/env python3

import argparse
import hashlib
import os
import pathlib
import platform
import shutil
import subprocess
import sys
from datetime import date

DEFAULT_GUI = True
DEFAULT_USER = "user"
DEFAULT_DRY = False
DEFAULT_DEV = False
DEFAULT_SHOW_DOCKERFILE = False

# The Linux distributions that we currently support.
# FIXME: Add a version mapping to avoid mistakes.
# FIXME: Maybe create an enum for these values.
DISTROS = ["debian", "fedora", "ubuntu"]
CONTAINER_RUNTIMES = ["podman", "docker"]
IMAGES_REGISTRY = "ghcr.io/freedomofpress/"
IMAGE_NAME_BUILD_DEV_FMT = (
    IMAGES_REGISTRY + "v2/dangerzone/build-dev/{distro}-{version}:{date}-{hash}"
)
IMAGE_NAME_BUILD_ENDUSER_FMT = (
    IMAGES_REGISTRY + "v2/dangerzone/end-user/{distro}-{version}:{date}-{hash}"
)

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

    env.py --distro ubuntu --version 22.04 run --dev bash
    user@dangerzone-dev:~$ cd dangerzone/
    user@dangerzone-dev:~$ poetry run ./dev_scripts/dangerzone

Run Dangerzone in the end-user environment:

    env.py --distro ubuntu --version 22.04 run dangerzone

"""

# XXX: overcome the fact that ubuntu images (starting on 23.04) ship with the 'ubuntu'
# user by default https://bugs.launchpad.net/cloud-images/+bug/2005129
# Related issue https://github.com/freedomofpress/dangerzone/pull/461
DOCKERFILE_UBUNTU_REM_USER = r"""
RUN touch /var/mail/ubuntu && chown ubuntu /var/mail/ubuntu && userdel -r ubuntu
"""

# On Ubuntu Jammy, use a different conmon version, as acquired from our apt-tools-prod
# repo. For more details, read:
# https://github.com/freedomofpress/dangerzone/issues/685
DOCKERFILE_CONMON_UPDATE = r"""
RUN apt-get update \
    && apt-get install -y ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY apt-tools-prod.sources /etc/apt/sources.list.d/
COPY apt-tools-prod.pref /etc/apt/preferences.d/
"""

# We are relying on Debian bullseye archived backports for testing only.
# They are not required to build or run Dangerzone but are useful to run
# the tests because they provide Qt6.
# See https://github.com/freedomofpress/dangerzone/issues/1213
DOCKERFILE_USE_BULLSEYE_BACKPORTS = r"""
RUN apt-get update && apt-get install -y ca-certificates
RUN echo "deb https://archive.debian.org/debian/ bullseye-backports main" \
    >> /etc/apt/sources.list
"""

# FIXME: Do we really need the python3-venv packages?
DOCKERFILE_BUILD_DEV_DEBIAN_DEPS = r"""
ARG DEBIAN_FRONTEND=noninteractive

# NOTE: Podman has several recommended packages that are actually essential for rootless
# containers. However, certain Podman versions (e.g., in Debian Trixie) bring Systemd in
# as a recommended dependency. The latter is a cause for problems, so we prefer to
# install only a subset of the recommended Podman packages. See also:
# https://github.com/freedomofpress/dangerzone/issues/689
RUN apt-get update \
    && apt-get install -y --no-install-recommends podman uidmap slirp4netns \
    && rm -rf /var/lib/apt/lists/*
RUN apt-get update \
    && apt-get install -y passt || echo "Skipping installation of passt package" \
    && rm -rf /var/lib/apt/lists/*
RUN apt-get update \
    && apt-get install -y --no-install-recommends dh-python make build-essential \
        git {qt_deps} pipx python3 python3-pip python3-venv dpkg-dev debhelper python3-setuptools \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pipx install poetry
RUN apt-get update \
    && apt-get install -y --no-install-recommends mupdf thunar \
    && rm -rf /var/lib/apt/lists/*
"""

# FIXME: Install Poetry on Fedora via package manager.
DOCKERFILE_BUILD_DEV_FEDORA_DEPS = r"""
RUN dnf install -y git rpm-build podman python3 python3-devel python3-poetry-core \
    pipx make qt6-qtbase-gui gcc gcc-c++\
    && dnf clean all

# FIXME: Drop this fix after it's resolved upstream.
# See https://github.com/freedomofpress/dangerzone/issues/286#issuecomment-1347149783
RUN rpm --restore shadow-utils

RUN dnf install -y mupdf thunar && dnf clean all
"""

# The Dockerfile for building a development environment for Dangerzone. Parts of the
# Dockerfile will be populated during runtime.
DOCKERFILE_BUILD_DEV = r"""FROM {distro}:{version}

{install_deps}

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

# Force Podman to use a specific configuration.
# See https://github.com/freedomofpress/dangerzone/issues/489
RUN mkdir -p /home/user/.config/containers
COPY storage.conf /home/user/.config/containers

# Install Poetry under ~/.local/bin.
# See https://github.com/freedomofpress/dangerzone/issues/351
# FIXME: pipx install poetry does not work for Ubuntu Focal.
ENV PATH="$PATH:/home/user/.local/bin"
RUN pipx install poetry
RUN pipx inject poetry poetry-plugin-export

COPY pyproject.toml poetry.lock /home/user/dangerzone/
RUN cd /home/user/dangerzone && poetry --no-ansi install
"""

DOCKERFILE_BUILD_DEBIAN_DEPS = r"""
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends mupdf thunar \
    && rm -rf /var/lib/apt/lists/*
"""

DOCKERFILE_BUILD_FEDORA_DEPS = r"""
RUN dnf install -y mupdf thunar && dnf clean all

# FIXME: Drop this fix after it's resolved upstream.
# See https://github.com/freedomofpress/dangerzone/issues/286#issuecomment-1347149783
RUN rpm --restore shadow-utils
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
RUN mkdir -p /home/user/.local/share/
WORKDIR /home/user

########################################
# Force Podman to use a specific configuration.
# See https://github.com/freedomofpress/dangerzone/issues/489
RUN mkdir -p /home/user/.config/containers
COPY storage.conf /home/user/.config/containers
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


def user_data():
    """Get the user data dir in (which differs on different OSes)"""
    home = pathlib.Path.home()
    system = platform.system()

    if system == "Windows":
        return home / "AppData" / "Local"
    elif system == "Linux":
        return home / ".local" / "share"
    elif system == "Darwin":
        return home / "Library" / "Application Support"


def dz_dev_root():
    """Get the directory where we will store dangerzone-dev related files"""
    return user_data() / "dangerzone-dev"


def distro_root(distro, version):
    """Get the root directory for the specific Linux environment."""
    return dz_dev_root() / "envs" / distro / version


def distro_state(distro, version):
    """Get the directory where we will store the state for the distro."""
    return distro_root(distro, version) / "state"


def distro_build(distro, version):
    """Get the directory where we will store the build files for the distro."""
    return distro_root(distro, version) / "build"


def get_current_date():
    return date.today().strftime("%Y-%m-%d")


def get_build_dir_sources(distro, version):
    """Return the files needed to build an image."""
    sources = [
        git_root() / "pyproject.toml",
        git_root() / "poetry.lock",
        git_root() / "dev_scripts" / "env.py",
        git_root() / "dev_scripts" / "storage.conf",
        git_root() / "dev_scripts" / "containers.conf",
    ]

    if distro == "ubuntu" and version in ("22.04", "jammy"):
        sources.extend(
            [
                git_root() / "dev_scripts" / "apt-tools-prod.pref",
                git_root() / "dev_scripts" / "apt-tools-prod.sources",
            ]
        )
    return sources


def image_name_build_dev(distro, version):
    """Get the container image for the dev variant of a Dangerzone environment."""
    hash = hash_files(get_build_dir_sources(distro, version))

    return IMAGE_NAME_BUILD_DEV_FMT.format(
        distro=distro, version=version, hash=hash, date=get_current_date()
    )


def image_name_build_enduser(distro, version):
    """Get the container image for the Dangerzone end-user environment."""

    hash = hash_files(get_files_in("install/linux", "debian"))
    return IMAGE_NAME_BUILD_ENDUSER_FMT.format(
        distro=distro, version=version, hash=hash, date=get_current_date()
    )


def dz_version():
    """Get the current Dangerzone version."""
    with open(git_root() / "share/version.txt") as f:
        return f.read().strip()


def hash_files(file_paths: list[pathlib.Path]) -> str:
    """Returns the hash value of a list of files using the sha256 hashing algorithm."""
    hash_obj = hashlib.new("sha256")
    for path in file_paths:
        with open(path, "rb") as file:
            file_data = file.read()
            hash_obj.update(file_data)

    return hash_obj.hexdigest()


def get_files_in(*folders: list[str]) -> list[pathlib.Path]:
    """Return the list of all files present in the given folders"""
    files = []
    for folder in folders:
        files.extend([p for p in (git_root() / folder).glob("**") if p.is_file()])
    return files


class Env:
    """A class that implements actions on Dangerzone environments"""

    def __init__(self, distro, version, runtime):
        """Initialize an Env class based on some common parameters."""
        self.distro = distro
        self.version = version

        # Try to autodetect the runtime, if the user has not provided it.
        podman_cmd = ["podman"]
        docker_cmd = ["docker"]
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

    def find_dz_package(self, path, pattern):
        """Get the full path of the Dangerzone package in the specified dir.

        There are times where we don't know the exact name of the Dangerzone package
        that we've built, e.g., because its patch level may have changed.

        Auto-detect the Dangerzone package based on a pattern that a user has provided,
        and fail if there are none, or multiple matches. If there's a single match, then
        return the full path for the package.
        """
        matches = list(path.glob(pattern))
        if len(matches) == 0:
            raise RuntimeError(
                f"Could not find Dangerzone package '{pattern}' in '{path}'"
            )
        elif len(matches) > 1:
            raise RuntimeError(
                f"Found more than one matches for Dangerzone package '{pattern}' in"
                f" '{path}'"
            )
        return matches[0]

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
            uidmaps = [
                "--uidmap",
                "1000:0:1",
                "--uidmap",
                "0:1:1000",
                "--uidmap",
                "1001:1001:64536",
            ]
            gidmaps = [
                "--gidmap",
                "1000:0:1",
                "--gidmap",
                "0:1:1000",
                "--gidmap",
                "1001:1001:64536",
            ]
            run_cmd += uidmaps + gidmaps

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
            "-v",
            f"{dist_state}/.local/share/dangerzone:/home/user/.local/share/dangerzone",
        ]

        run_cmd += ["-u", user]

        # Select the proper container image based on whether the user wants to run the
        # command in a dev or end-user environment.
        if dev:
            run_cmd += [
                "--hostname",
                "dangerzone-dev",
                image_name_build_dev(self.distro, self.version),
            ]
        else:
            run_cmd += [
                "--hostname",
                "dangerzone",
                image_name_build_enduser(self.distro, self.version),
            ]

        run_cmd += cmd

        # If the user has asked to perform a dry-run, then print the command that the
        # script would use internally.
        if dry:
            print(" ".join(self.runtime_cmd + list(run_cmd)))
            return

        dist_state.mkdir(parents=True, exist_ok=True)
        (dist_state / "containers").mkdir(exist_ok=True)

        (dist_state / ".local" / "share" / "dangerzone").mkdir(
            parents=True, exist_ok=True
        )
        (dist_state / ".bash_history").touch(exist_ok=True)
        self.runtime_run(*run_cmd)

    def pull_image_from_registry(self, image):
        try:
            subprocess.run(self.runtime_cmd + ["pull", image], check=True)
            return True
        except subprocess.CalledProcessError:
            # Do not log an error here, we are just checking if the image exists
            # on the registry.
            return False

    def push_image_to_registry(self, image):
        try:
            subprocess.run(self.runtime_cmd + ["push", image], check=True)
            return True
        except subprocess.CalledProcessError as e:
            print("An error occured when pulling the image: ", e)
            return False

    def build_dev(self, show_dockerfile=DEFAULT_SHOW_DOCKERFILE, sync=False):
        """Build a Linux environment and install tools for Dangerzone development."""
        image = image_name_build_dev(self.distro, self.version)

        if sync and self.pull_image_from_registry(image):
            print("Image has been pulled from the registry, no need to build it.")
            return
        elif sync:
            print("Image label not in registry, building it")

        if self.distro == "fedora":
            install_deps = DOCKERFILE_BUILD_DEV_FEDORA_DEPS
        else:
            # Use Qt6 in all of our Linux dev environments, and add a missing
            # libxcb-cursor0 dependency
            #
            # See https://github.com/freedomofpress/dangerzone/issues/482
            qt_deps = "libqt6gui6 libxcb-cursor0"
            install_deps = DOCKERFILE_BUILD_DEV_DEBIAN_DEPS
            if self.distro == "ubuntu" and self.version in ("22.04", "jammy"):
                # Ubuntu Jammy misses a dependency to `libxkbcommon-x11-0`, which we can
                # install indirectly via `qt6-qpa-plugins`.
                qt_deps += " qt6-qpa-plugins"
                # Ubuntu Jammy requires a more up-to-date conmon package
                # (see https://github.com/freedomofpress/dangerzone/issues/685)
                install_deps = (
                    DOCKERFILE_CONMON_UPDATE + DOCKERFILE_BUILD_DEV_DEBIAN_DEPS
                )
            elif self.distro == "ubuntu" and self.version in (
                "24.04",
                "noble",
                "25.04",
                "plucky",
            ):
                install_deps = (
                    DOCKERFILE_UBUNTU_REM_USER + DOCKERFILE_BUILD_DEV_DEBIAN_DEPS
                )
            elif self.distro == "debian" and self.version in ("bullseye",):
                # Debian Bullseye misses a dependency to libgl1.
                qt_deps += " libgl1"

                install_deps = (
                    DOCKERFILE_USE_BULLSEYE_BACKPORTS + DOCKERFILE_BUILD_DEV_DEBIAN_DEPS
                )

            install_deps = install_deps.format(qt_deps=qt_deps)

        dockerfile = DOCKERFILE_BUILD_DEV.format(
            distro=self.distro, version=self.version, install_deps=install_deps
        )
        if show_dockerfile:
            print(dockerfile)
            return

        build_dir = distro_build(self.distro, self.version)
        os.makedirs(build_dir, exist_ok=True)

        # Populate the build context.
        for source in get_build_dir_sources(self.distro, self.version):
            shutil.copy(source, build_dir)

        with open(build_dir / "Dockerfile", mode="w") as f:
            f.write(dockerfile)

        self.runtime_run("build", "-t", image, build_dir)

        if sync:
            if not self.push_image_to_registry(image):
                print("An error occured while trying to push to the container registry")

    def build(
        self,
        show_dockerfile=DEFAULT_SHOW_DOCKERFILE,
    ):
        """Build a Linux environment and install Dangerzone in it."""
        build_dir = distro_build(self.distro, self.version)
        os.makedirs(build_dir, exist_ok=True)
        version = dz_version()
        if self.distro == "fedora":
            install_deps = DOCKERFILE_BUILD_FEDORA_DEPS
            package_pattern = f"dangerzone-{version}-*.fc{self.version}.x86_64.rpm"
            package_src = self.find_dz_package(git_root() / "dist", package_pattern)
            package = package_src.name
            package_dst = build_dir / package
            install_cmd = "dnf install -y"
        else:
            install_deps = DOCKERFILE_BUILD_DEBIAN_DEPS
            if self.distro == "ubuntu" and self.version in ("22.04", "jammy"):
                # Ubuntu Jammy requires a more up-to-date conmon
                # package (see https://github.com/freedomofpress/dangerzone/issues/685)
                install_deps = DOCKERFILE_CONMON_UPDATE + DOCKERFILE_BUILD_DEBIAN_DEPS
            elif self.distro == "ubuntu" and self.version in (
                "24.04",
                "noble",
                "25.04",
                "plucky",
            ):
                install_deps = DOCKERFILE_UBUNTU_REM_USER + DOCKERFILE_BUILD_DEBIAN_DEPS
            package_pattern = f"dangerzone_{version}-*_*.deb"
            package_src = self.find_dz_package(git_root() / "deb_dist", package_pattern)
            package = package_src.name
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

        # Populate the build context.
        shutil.copy(package_src, package_dst)
        shutil.copy(git_root() / "dev_scripts" / "storage.conf", build_dir)
        shutil.copy(git_root() / "dev_scripts" / "containers.conf", build_dir)
        if self.distro == "ubuntu" and self.version in ("22.04", "jammy"):
            shutil.copy(git_root() / "dev_scripts" / "apt-tools-prod.pref", build_dir)
            shutil.copy(
                git_root() / "dev_scripts" / "apt-tools-prod.sources", build_dir
            )
        with open(build_dir / "Dockerfile", mode="w") as f:
            f.write(dockerfile)

        image = image_name_build_enduser(self.distro, self.version)
        self.runtime_run("build", "-t", image, build_dir)


def env_run(args):
    """Invoke the 'run' command based on the CLI args."""
    if not args.command:
        print("Please provide a command for the environment")
        sys.exit(1)

    env = Env.from_args(args)
    return env.run(
        args.command, gui=args.gui, user=args.user, dry=args.dry, dev=args.dev
    )


def env_build_dev(args):
    """Invoke the 'build-dev' command based on the CLI args."""
    env = Env.from_args(args)
    return env.build_dev(show_dockerfile=args.show_dockerfile, sync=args.sync)


def env_build(args):
    """Invoke the 'build' command based on the CLI args."""
    env = Env.from_args(args)
    return env.build(
        show_dockerfile=args.show_dockerfile,
    )


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
        "--no-gui",
        default=DEFAULT_GUI,
        action="store_false",
        dest="gui",
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
    parser_build_dev.add_argument(
        "--sync",
        default=False,
        action="store_true",
        help="Attempt to pull the image, build it if not found and push it to the container registry",
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

#!/usr/bin/env python3

import argparse
import functools
import os
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.request

DEFAULT_GUI = True
DEFAULT_USER = "user"
DEFAULT_DRY = False
DEFAULT_DEV = False
DEFAULT_SHOW_DOCKERFILE = False
DEFAULT_DOWNLOAD_PYSIDE6 = False

PYSIDE6_RPM = "python3-pyside6-{pyside6_version}-1.fc{fedora_version}.x86_64.rpm"
PYSIDE6_URL = (
    "https://packages.freedom.press/yum-tools-prod/dangerzone/f{fedora_version}/%s"
    % PYSIDE6_RPM
)

PYSIDE6_DL_MESSAGE = """\
Downloading PySide6 RPM from:

    {pyside6_url}

into the following local path:

    {pyside6_local_path}

The RPM is over 100 MB, so this operation may take a while...
"""

PYSIDE6_NOT_FOUND_ERROR = """\
The following package is not present in your system:

    {pyside6_local_path}

You can build it locally and copy it in the expected path, following the instructions
in:

    https://github.com/freedomofpress/python3-pyside6-rpm

Alternatively, you can rerun the command adding the '--download-pyside6' flag, which
will download it from:

    {pyside6_url}
"""

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

    env.py --distro ubuntu --version 22.04 run --dev bash
    user@dangerzone-dev:~$ cd dangerzone/
    user@dangerzone-dev:~$ poetry run ./dev/scripts/dangerzone

Run Dangerzone in the end-user environment:

    env.py --distro ubuntu --version 22.04 run dangerzone

"""

# NOTE: For Ubuntu 20.04 specifically, we need to install some extra deps, mainly for
# Podman. This needs to take place both in our dev and end-user environment. See the
# corresponding note in our Installation section:
#
# https://github.com/freedomofpress/dangerzone/blob/main/INSTALL.md#ubuntu-debian
DOCKERFILE_UBUNTU_2004_DEPS = r"""
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y python-all curl wget gnupg2 \
    && rm -rf /var/lib/apt/lists/*
RUN . /etc/os-release \
    && sh -c "echo 'deb http://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable/xUbuntu_$VERSION_ID/ /' \
        > /etc/apt/sources.list.d/devel:kubic:libcontainers:stable.list" \
    && wget -nv https://download.opensuse.org/repositories/devel:kubic:libcontainers:stable/xUbuntu_$VERSION_ID/Release.key -O- \
        | apt-key add -
"""

# XXX: overcome the fact that ubuntu images (starting on 23.04) ship with the 'ubuntu'
# user by default https://bugs.launchpad.net/cloud-images/+bug/2005129
# Related issue https://github.com/freedomofpress/dangerzone/pull/461
DOCKERFILE_UBUNTU_REM_USER = r"""
RUN touch /var/mail/ubuntu && chown ubuntu /var/mail/ubuntu && userdel -r ubuntu
"""

# On Ubuntu Jammy / Debian Bullseye, use a different conmon version, as acquired from
# Debian's oldstable proposed updates. For more details, read:
# https://github.com/freedomofpress/dangerzone/issues/685
DOCKERFILE_CONMON_UPDATE = r"""
COPY oldstable-pu.sources /etc/apt/sources.list.d/
COPY oldstable-pu.pref /etc/apt/preferences.d/
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
    && apt-get install -y --no-install-recommends dh-python make build-essential \
        git fakeroot {qt_deps} pipx python3 python3-dev python3-venv python3-stdeb \
        python3-all \
    && rm -rf /var/lib/apt/lists/*
# NOTE: `pipx install poetry` fails on Ubuntu Focal, when installed through APT. By
# installing the latest version, we sidestep this issue.
RUN bash -c 'if [[ "$(pipx --version)" < "1" ]]; then \
                apt-get update \
                && apt-get remove -y pipx \
                && apt-get install -y --no-install-recommends python3-pip \
                && pip install pipx \
                && rm -rf /var/lib/apt/lists/*; \
              else true; fi'
RUN apt-get update \
    && apt-get install -y --no-install-recommends mupdf \
    && rm -rf /var/lib/apt/lists/*
"""

# FIXME: Install Poetry on Fedora via package manager.
DOCKERFILE_BUILD_DEV_FEDORA_DEPS = r"""
RUN dnf install -y git rpm-build podman python3 python3-devel python3-poetry-core \
    pipx make qt6-qtbase-gui \
    && dnf clean all

# FIXME: Drop this fix after it's resolved upstream.
# See https://github.com/freedomofpress/dangerzone/issues/286#issuecomment-1347149783
RUN rpm --restore shadow-utils

RUN dnf install -y mupdf && dnf clean all
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

COPY pyproject.toml poetry.lock /home/user/dangerzone/
RUN cd /home/user/dangerzone && poetry --no-ansi install
"""

DOCKERFILE_BUILD_DEBIAN_DEPS = r"""
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends mupdf \
    && rm -rf /var/lib/apt/lists/*
"""

DOCKERFILE_BUILD_FEDORA_39_DEPS = r"""
COPY {pyside6_rpm} /tmp/pyside6.rpm
RUN dnf install -y /tmp/pyside6.rpm
"""

DOCKERFILE_BUILD_FEDORA_DEPS = r"""
RUN dnf install -y mupdf && dnf clean all

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


class PySide6Manager:
    """Provision PySide6 RPMs in our Dangerzone environments.

    This class holds all the logic around checking and downloading PySide RPMs. It can
    detect the PySide6 version that the project requires, check if an RPM is present
    under "/dist", and download it.
    """

    def __init__(self, distro_name, distro_version):
        if distro_name != "fedora":
            raise RuntimeError("Managing PySide6 RPMs is available only in Fedora")
        self.distro_name = distro_name
        self.distro_version = distro_version

    @property
    @functools.lru_cache
    def version(self):
        """Retrieve the PySide6 version from poetry.lock.

        Read the poetry.lock file, and grep the version of the PySide6 library. The
        results of this method call are cached, so we can call it repeatedly without any
        performance cost.
        """
        # FIXME: I don't like regexes, but problem is that `tomllib` is not present in
        # Python < 3.11. So, since we don't want to rely on an external library yet, we
        # have to resort to regexes. Note that the regex we choose uses Shiboken6,
        # mainly because the PySide6 package and its version are in different lines.
        with open(git_root() / "poetry.lock") as f:
            toml = f.read()
            match = re.search(r'^shiboken6 = "([\d.]+)"$', toml, re.MULTILINE)
            return match.groups()[0]

    @property
    def rpm_name(self):
        """The name of the PySide6 RPM."""
        return PYSIDE6_RPM.format(
            pyside6_version=self.version, fedora_version=self.distro_version
        )

    @property
    def rpm_url(self):
        """The URL of the PySide6 RPM, as hosted in FPF's RPM repo."""
        return PYSIDE6_URL.format(
            pyside6_version=self.version,
            fedora_version=self.distro_version,
        )

    @property
    def rpm_local_path(self):
        """The local path where this script will look for the PySide6 RPM."""
        return git_root() / "dist" / self.rpm_name

    @property
    def is_rpm_present(self):
        """Check if PySide6 RPM is present in the user's system."""
        return self.rpm_local_path.exists()

    def download_rpm(self):
        """Download PySide6 from FPF's RPM repo."""
        print(
            PYSIDE6_DL_MESSAGE.format(
                pyside6_url=self.rpm_url,
                pyside6_local_path=self.rpm_local_path,
            ),
            file=sys.stderr,
        )
        try:
            with urllib.request.urlopen(self.rpm_url) as r, open(
                self.rpm_local_path, "wb"
            ) as f:
                shutil.copyfileobj(r, f)
        except:
            # NOTE: We purposefully catch all exceptions, since we want to catch Ctrl-C
            # as well.
            print("Download interrupted, removing file", file=sys.stderr)
            self.rpm_local_path.unlink()
            raise
        print("PySide6 was downloaded successfully", file=sys.stderr)


class Env:
    """A class that implements actions on Dangerzone environments"""

    def __init__(self, distro, version, runtime):
        """Initialize an Env class based on some common parameters."""
        self.distro = distro
        self.version = version
        # NOTE: We change "bullseye" to "bullseye-backports", since it contains `pipx`,
        # which is not available through the original repos.
        if self.distro == "debian" and self.version in ("bullseye", "11"):
            self.version = "bullseye-backports"

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

        dist_state.mkdir(parents=True, exist_ok=True)
        (dist_state / "containers").mkdir(exist_ok=True)
        (dist_state / ".bash_history").touch(exist_ok=True)
        self.runtime_run(*run_cmd)

    def build_dev(self, show_dockerfile=DEFAULT_SHOW_DOCKERFILE):
        """Build a Linux environment and install tools for Dangerzone development."""
        if self.distro == "fedora":
            install_deps = DOCKERFILE_BUILD_DEV_FEDORA_DEPS
        else:
            # Use Qt6 in all of our Linux dev environments, and add a missing
            # libxcb-cursor0 dependency
            #
            # See https://github.com/freedomofpress/dangerzone/issues/482
            qt_deps = "libqt6gui6 libxcb-cursor0"
            install_deps = DOCKERFILE_BUILD_DEV_DEBIAN_DEPS
            if self.distro == "ubuntu" and self.version in ("20.04", "focal"):
                qt_deps = "libqt5gui5 libxcb-cursor0"  # Ubuntu Focal has only Qt5.
                install_deps = (
                    DOCKERFILE_UBUNTU_2004_DEPS + DOCKERFILE_BUILD_DEV_DEBIAN_DEPS
                )
            elif self.distro == "ubuntu" and self.version in ("22.04", "jammy"):
                # Ubuntu Jammy misses a dependency to `libxkbcommon-x11-0`, which we can
                # install indirectly via `qt6-qpa-plugins`.
                qt_deps += " qt6-qpa-plugins"
                # Ubuntu Jammy and Debian Bullseye require a more up-to-date conmon
                # package (see https://github.com/freedomofpress/dangerzone/issues/685)
                install_deps = (
                    DOCKERFILE_CONMON_UPDATE + DOCKERFILE_BUILD_DEV_DEBIAN_DEPS
                )
            elif self.distro == "ubuntu" and self.version in (
                "23.04",
                "23.10",
                "lunar",
                "mantic",
            ):
                install_deps = (
                    DOCKERFILE_UBUNTU_REM_USER + DOCKERFILE_BUILD_DEV_DEBIAN_DEPS
                )
            elif self.distro == "debian" and self.version in ("bullseye-backports",):
                # Debian Bullseye misses a dependency to libgl1.
                qt_deps += " libgl1"
                # Ubuntu Jammy and Debian Bullseye require a more up-to-date conmon
                # package (see https://github.com/freedomofpress/dangerzone/issues/685)
                install_deps = (
                    DOCKERFILE_CONMON_UPDATE + DOCKERFILE_BUILD_DEV_DEBIAN_DEPS
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
        shutil.copy(git_root() / "pyproject.toml", build_dir)
        shutil.copy(git_root() / "poetry.lock", build_dir)
        shutil.copy(git_root() / "dev_scripts" / "storage.conf", build_dir)
        if self.distro in ("debian", "ubuntu"):
            shutil.copy(git_root() / "dev_scripts" / "oldstable-pu.pref", build_dir)
            shutil.copy(
                git_root() / "dev_scripts" / f"oldstable-pu-{self.distro}.sources",
                build_dir / "oldstable-pu.sources",
            )
        with open(build_dir / "Dockerfile", mode="w") as f:
            f.write(dockerfile)

        image = image_name_build(self.distro, self.version)
        self.runtime_run("build", "-t", image, build_dir)

    def build(
        self,
        show_dockerfile=DEFAULT_SHOW_DOCKERFILE,
        download_pyside6=DEFAULT_DOWNLOAD_PYSIDE6,
    ):
        """Build a Linux environment and install Dangerzone in it."""
        build_dir = distro_build(self.distro, self.version)
        version = dz_version()
        if self.distro == "fedora":
            install_deps = DOCKERFILE_BUILD_FEDORA_DEPS
            package = f"dangerzone-{version}-1.fc{self.version}.x86_64.rpm"
            package_src = git_root() / "dist" / package
            package_dst = build_dir / package
            install_cmd = "dnf install -y"

            # NOTE: For Fedora 39+ onward, we check if a PySide6 RPM package exists in
            # the user's system. If not, we either throw an error or download it from
            # FPF's repo, according to the user's choice.
            # FIXME: Unconditionally check for PySide6, once Fedora 38 is no longer
            # supported.
            if self.version != "38":
                pyside6 = PySide6Manager(self.distro, self.version)
                if not pyside6.is_rpm_present:
                    if download_pyside6:
                        pyside6.download_rpm()
                    else:
                        print(
                            PYSIDE6_NOT_FOUND_ERROR.format(
                                pyside6_local_path=pyside6.rpm_local_path,
                                pyside6_url=pyside6.rpm_url,
                            ),
                            file=sys.stderr,
                        )
                        return 1
                shutil.copy(pyside6.rpm_local_path, build_dir / pyside6.rpm_name)
                install_deps = (
                    DOCKERFILE_BUILD_FEDORA_DEPS + DOCKERFILE_BUILD_FEDORA_39_DEPS
                ).format(pyside6_rpm=pyside6.rpm_name)
        else:
            install_deps = DOCKERFILE_BUILD_DEBIAN_DEPS
            if self.distro == "ubuntu" and self.version in ("20.04", "focal"):
                install_deps = (
                    DOCKERFILE_UBUNTU_2004_DEPS + DOCKERFILE_BUILD_DEBIAN_DEPS
                )
            elif (self.distro == "ubuntu" and self.version in ("22.04", "jammy")) or (
                self.distro == "debian" and self.version in ("bullseye-backports",)
            ):
                # Ubuntu Jammy and Debian Bullseye require a more up-to-date conmon
                # package (see https://github.com/freedomofpress/dangerzone/issues/685)
                install_deps = DOCKERFILE_CONMON_UPDATE + DOCKERFILE_BUILD_DEBIAN_DEPS
            elif self.distro == "ubuntu" and self.version in (
                "23.04",
                "23.10",
                "lunar",
                "mantic",
            ):
                install_deps = DOCKERFILE_UBUNTU_REM_USER + DOCKERFILE_BUILD_DEBIAN_DEPS
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
        shutil.copy(git_root() / "dev_scripts" / "storage.conf", build_dir)
        if self.distro in ("debian", "ubuntu"):
            shutil.copy(git_root() / "dev_scripts" / "oldstable-pu.pref", build_dir)
            shutil.copy(
                git_root() / "dev_scripts" / f"oldstable-pu-{self.distro}.sources",
                build_dir / "oldstable-pu.sources",
            )
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
    return env.run(
        args.command, gui=args.gui, user=args.user, dry=args.dry, dev=args.dev
    )


def env_build_dev(args):
    """Invoke the 'build-dev' command based on the CLI args."""
    env = Env.from_args(args)
    return env.build_dev(show_dockerfile=args.show_dockerfile)


def env_build(args):
    """Invoke the 'build' command based on the CLI args."""
    env = Env.from_args(args)
    return env.build(
        show_dockerfile=args.show_dockerfile,
        download_pyside6=args.download_pyside6,
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
    parser_build.add_argument(
        "--download-pyside6",
        default=DEFAULT_DOWNLOAD_PYSIDE6,
        action="store_true",
        help="Download PySide6 from FPF's RPM repo",
    )

    return parser.parse_args()


def main():
    args = parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

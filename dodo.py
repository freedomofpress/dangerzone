import json
import os
import platform
import shutil
from pathlib import Path

from doit.action import CmdAction

ARCH = "arm64" if platform.machine() == "arm64" else "i686"
VERSION = open("share/version.txt").read().strip()
FEDORA_VERSIONS = ["41", "42", "43"]

### Global parameters

CONTAINER_RUNTIME = os.environ.get("CONTAINER_RUNTIME", "podman")
DEFAULT_RELEASE_DIR = Path.home() / "release-assets" / VERSION
RELEASE_DIR = Path(os.environ.get("RELEASE_DIR", DEFAULT_RELEASE_DIR))
APPLE_ID = os.environ.get("APPLE_ID", None)

### Task Parameters

PARAM_APPLE_ID = {
    "name": "apple_id",
    "long": "apple-id",
    "default": APPLE_ID,
    "help": "The Apple developer ID that will be used to sign the .dmg",
}

### File dependencies
#
# Define all the file dependencies for our tasks in a single place, since some file
# dependencies are shared between tasks.


def list_files(path, recursive=False):
    """List files in a directory, and optionally traverse into subdirectories."""
    glob_fn = Path(path).rglob if recursive else Path(path).glob
    return [f for f in glob_fn("*") if f.is_file() and not f.suffix == ".pyc"]


ASSETS_DEPS = ["mazette.lock"]

# NOTE: The container image is a major dependency of our assets, and we would ideally
# want to track it with its hash. In practice though, what we need here is to bust
# doit's cache, when the `latest` tag changes. So, an alternative way to do it without
# pinning the hash is to monitor changes to the LAST_KNOWN_LOG_INDEX of
# dangerzone/updater/log_index.py, which is unique per image.
IMAGE_DEPS = ["dangerzone/updater/log_index.py"]

SOURCE_DEPS = [
    *list_files("assets"),
    *list_files("share"),
    *list_files("dangerzone", recursive=True),
]

PYTHON_DEPS = ["poetry.lock", "pyproject.toml"]

DMG_DEPS = [
    *list_files("install/macos"),
    *PYTHON_DEPS,
    *SOURCE_DEPS,
    *ASSETS_DEPS,
]

LINUX_DEPS = [
    *list_files("install/linux"),
    *PYTHON_DEPS,
    *SOURCE_DEPS,
    *ASSETS_DEPS,
]

DEB_DEPS = [*LINUX_DEPS, *list_files("debian")]
RPM_DEPS = [*LINUX_DEPS, *list_files("qubes")]


def copy_dir(src, dst):
    """Copy a directory to a destination dir, and overwrite it if it exists."""
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst)


def create_release_dir():
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    (RELEASE_DIR / "tmp").mkdir(exist_ok=True)


def prepare_dz_dir(dz_dir, full=False):
    """Prepare a Git repo for building artifacts.

    This function creates a pristine Dangerzone repo out of the local one, by copying
    the Git repo, and doing the following actions on the new directory:
    1. Clean untracked files with `git clean -fdx`
    2. Copy the container image under `share/container.tar` (only if full=True)
    3. Install the GitHub assets for this platform

    The above actions should be quite fast, because they just copy files around. That
    applies to the downloading of the GitHub assets with mazette, since it caches file
    downloads internally.
    """
    arch = "arm64" if ARCH == "arm64" else "amd64"
    mazette_platform = f"darwin/{arch}" if dz_dir.name == "macos" else f"linux/{arch}"
    img_src = RELEASE_DIR / f"container-{VERSION}-{ARCH}.tar"
    img_dst = dz_dir / "share" / "container.tar"

    actions = [
        (copy_dir, [".", dz_dir]),
        f"cd {dz_dir} && git clean -fdx",
    ]
    if full:
        actions.append(["cp", img_src, img_dst])
    actions.append(
        [
            "poetry",
            "run",
            "mazette",
            "install",
            "-d",
            dz_dir,
            "--platform",
            mazette_platform,
        ]
    )
    return actions


def build_linux_pkg(distro, version, cwd, qubes=False, full=False):
    """Generic command for building a .deb/.rpm in a Dangerzone dev environment."""
    pkg = "rpm" if distro == "fedora" else "deb"
    cmd = [
        "python3",
        "./dev_scripts/env.py",
        "--distro",
        distro,
        "--version",
        version,
        "run",
        "--no-gui",
        "--dev",
        f"./dangerzone/install/linux/build-{pkg}.py",
    ]
    if qubes:
        cmd += ["--qubes"]
    if full:
        cmd += ["--full"]
    return CmdAction(" ".join(cmd), cwd=cwd)


def build_deb(cwd, full=False):
    """Build a .deb package on Debian Bookworm."""
    return build_linux_pkg(distro="debian", version="bookworm", cwd=cwd, full=full)


def build_rpm(version, cwd, qubes=False, full=False):
    """Build an .rpm package on the requested Fedora distro."""
    return build_linux_pkg(distro="fedora", version=version, cwd=cwd, qubes=qubes, full=full)


### Tasks


def task_clean_container_runtime():
    """Clean the storage space of the container runtime."""
    return {
        "actions": None,
        "clean": [
            [CONTAINER_RUNTIME, "system", "prune", "-a", "-f"],
        ],
    }


def task_check_container_runtime():
    """Test that the container runtime is ready."""
    return {
        "actions": [
            ["which", CONTAINER_RUNTIME],
            [CONTAINER_RUNTIME, "ps"],
        ],
    }


def task_macos_check_cert():
    """Test that the Apple developer certificate can be used."""
    return {
        "actions": [
            "xcrun notarytool history --apple-id %(apple_id)s --keychain-profile dz-notarytool-release-key"
        ],
        "params": [PARAM_APPLE_ID],
    }


def task_macos_check_system():
    """Run macOS specific system checks, as well as the generic ones."""
    return {
        "actions": None,
        "task_dep": ["check_container_runtime", "macos_check_cert"],
    }


def task_init_release_dir():
    """Create a directory for release artifacts."""
    return {
        "actions": [create_release_dir],
        "clean": [f"rm -rf {RELEASE_DIR}"],
    }


def task_download_cosign(distro=None):
    """Download the cosign binary under share/vendor."""
    return {
        "actions": ["poetry run mazette install cosign"],
        "file_dep": ASSETS_DEPS,
        "task_dep": ["poetry_install"],
        "targets": ["share/vendor/cosign"],
        "clean": True,
    }


def task_download_image():
    """Download the container image using dangerzone-image prepare-archive"""
    img_dst = RELEASE_DIR / f"container-{VERSION}-{ARCH}.tar"

    return {
        "actions": [
            f"poetry run ./dev_scripts/dangerzone-image prepare-archive --output {img_dst}",
        ],
        "targets": [
            img_dst,
        ],
        "file_dep": IMAGE_DEPS,
        "task_dep": ["init_release_dir", "poetry_install", "download_cosign"],
        "clean": True,
    }


def task_poetry_install():
    """Setup the Poetry environment"""
    return {"actions": ["poetry sync"], "clean": ["poetry env remove --all"]}


def task_macos_build_dmg():
    """Build the macOS .dmg file for Dangerzone."""
    dz_dir = RELEASE_DIR / "tmp" / "macos"
    dmg_src = dz_dir / "dist" / "Dangerzone.dmg"
    dmg_dst = RELEASE_DIR / f"Dangerzone-{VERSION}-{ARCH}.dmg"  # FIXME: Add -arch

    return {
        "actions": [
            *prepare_dz_dir(dz_dir),
            f"cd {dz_dir} && poetry run install/macos/build-app.py --with-codesign",
            (
                "xcrun notarytool submit --wait --apple-id %(apple_id)s"
                f" --keychain-profile dz-notarytool-release-key {dmg_src}"
            ),
            f"xcrun stapler staple {dmg_src}",
            ["cp", dmg_src, dmg_dst],
            ["rm", "-rf", dz_dir],
        ],
        "params": [PARAM_APPLE_ID],
        "file_dep": DMG_DEPS,
        "task_dep": [
            "macos_check_system",
            "init_release_dir",
            "poetry_install",
            "download_image",
        ],
        "targets": [dmg_src, dmg_dst],
        "clean": True,
    }


def task_debian_env():
    """Build a Debian Bookworm dev environment."""
    return {
        "actions": [
            [
                "python3",
                "./dev_scripts/env.py",
                "--distro",
                "debian",
                "--version",
                "bookworm",
                "build-dev",
            ]
        ],
        "task_dep": ["check_container_runtime"],
    }


def task_debian_deb():
    """Build Debian packages for Debian Bookworm."""
    for full in (False, True):
        full_ident = "-full" if full else ""
        full_desc = " (full)" if full else ""
        dz_dir = RELEASE_DIR / "tmp" / f"debian{full_ident}"
        pkg_name = f"dangerzone{full_ident}"
        deb_name = f"{pkg_name}_{VERSION}-1_amd64.deb"
        deb_src = dz_dir / "deb_dist" / deb_name
        deb_dst = RELEASE_DIR / deb_name

        task_deps = [
            "init_release_dir",
            "poetry_install",
            "debian_env",
        ]
        if full:
            task_deps.append("download_image")
        else:
            # Ensure full build doesn't run in parallel with default build,
            # as both modify the same debian/ files during the build process.
            task_deps.append("debian_deb:default")

        yield {
            "name": "full" if full else "default",
            "doc": f"Build a Debian Bookworm package{full_desc}",
            "actions": [
                *prepare_dz_dir(dz_dir, full=full),
                build_deb(cwd=dz_dir, full=full),
                ["cp", deb_src, deb_dst],
                ["rm", "-rf", dz_dir],
            ],
            "file_dep": DEB_DEPS,
            "task_dep": task_deps,
            "targets": [deb_dst],
            "clean": True,
        }


def task_fedora_env():
    """Build Fedora dev environments."""
    for version in FEDORA_VERSIONS:
        yield {
            "name": version,
            "doc": f"Build Fedora {version} dev environments",
            "actions": [
                [
                    "python3",
                    "./dev_scripts/env.py",
                    "--distro",
                    "fedora",
                    "--version",
                    version,
                    "build-dev",
                ],
            ],
            "task_dep": ["check_container_runtime"],
        }


def task_fedora_rpm():
    """Build Fedora packages for every supported version."""
    # Build variants: regular, qubes, and full (full and qubes are mutually exclusive)
    variants = [
        {"qubes": False, "full": False},
        {"qubes": True, "full": False},
        {"qubes": False, "full": True},
    ]
    for version in FEDORA_VERSIONS:
        for variant in variants:
            qubes = variant["qubes"]
            full = variant["full"]
            variant_ident = "-qubes" if qubes else ("-full" if full else "")
            variant_desc = " for Qubes" if qubes else (" (full)" if full else "")
            dz_dir = RELEASE_DIR / "tmp" / f"f{version}{variant_ident}"
            rpm_names = [
                f"dangerzone{variant_ident}-{VERSION}-1.fc{version}.x86_64.rpm",
                f"dangerzone{variant_ident}-{VERSION}-1.fc{version}.src.rpm",
            ]
            rpm_src = [dz_dir / "dist" / rpm_name for rpm_name in rpm_names]
            rpm_dst = [RELEASE_DIR / rpm_name for rpm_name in rpm_names]

            task_deps = [
                "init_release_dir",
                "poetry_install",
                f"fedora_env:{version}",
            ]
            if full:
                task_deps.append("download_image")

            yield {
                "name": version + variant_ident,
                "doc": f"Build a Fedora {version} package{variant_desc}",
                "actions": [
                    *prepare_dz_dir(dz_dir, full=full),
                    build_rpm(version, cwd=dz_dir, qubes=qubes, full=full),
                    ["cp", *rpm_src, RELEASE_DIR],
                    ["rm", "-rf", dz_dir],
                ],
                "file_dep": RPM_DEPS,
                "task_dep": task_deps,
                "targets": rpm_dst,
                "clean": True,
            }


def task_git_archive():
    """Build a Git archive of the repo."""
    target = f"{RELEASE_DIR}/dangerzone-{VERSION}.tar.gz"
    return {
        "actions": [
            f"git archive --format=tar.gz -o {target} --prefix=dangerzone/ HEAD"
        ],
        "targets": [target],
        "task_dep": ["init_release_dir"],
    }


#######################################################################################
#
#                              END OF TASKS
#
# The following task should be the LAST one in the dodo file, so that it runs first when
# running `do clean`.


def clean_prompt():
    ans = input(
        f"""
You have not specified a target to clean.
This means that doit will clean the following targets:

* ALL the containers, images, and build cache in {CONTAINER_RUNTIME.capitalize()}
* ALL the built targets and directories

For a full list of the targets that doit will clean, run: doit clean --dry-run

Are you sure you want to clean everything (y/N): \
"""
    )
    if ans.lower() in ["yes", "y"]:
        return
    else:
        print("Exiting...")
        exit(1)


def task_clean_prompt():
    """Make sure that the user really wants to run the clean tasks."""
    return {
        "actions": None,
        "clean": [clean_prompt],
    }

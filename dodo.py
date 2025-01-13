import json
import os
import platform
import shutil
from pathlib import Path

from doit.action import CmdAction

ARCH = "arm64" if platform.machine() == "arm64" else "i686"
VERSION = open("share/version.txt").read().strip()
FEDORA_VERSIONS = ["40", "41"]
DEBIAN_VERSIONS = ["bullseye", "focal", "jammy", "mantic", "noble", "trixie"]

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


def list_language_data():
    """List the expected language data that Dangerzone downloads and stores locally."""
    tessdata_dir = Path("share") / "tessdata"
    langs = json.loads(open(tessdata_dir.parent / "ocr-languages.json").read()).values()
    targets = [tessdata_dir / f"{lang}.traineddata" for lang in langs]
    targets.append(tessdata_dir)
    return targets


TESSDATA_DEPS = ["install/common/download-tessdata.py", "share/ocr-languages.json"]
TESSDATA_TARGETS = list_language_data()

IMAGE_DEPS = [
    "Dockerfile",
    *list_files("dangerzone/conversion"),
    *list_files("dangerzone/container_helpers"),
    "install/common/build-image.py",
]
IMAGE_TARGETS = ["share/container.tar.gz", "share/image-id.txt"]

SOURCE_DEPS = [
    *list_files("assets"),
    *list_files("share"),
    *list_files("dangerzone", recursive=True),
]

PYTHON_DEPS = ["poetry.lock", "pyproject.toml"]

DMG_DEPS = [
    *list_files("install/macos"),
    *TESSDATA_TARGETS,
    *IMAGE_TARGETS,
    *PYTHON_DEPS,
    *SOURCE_DEPS,
]

LINUX_DEPS = [
    *list_files("install/linux"),
    *IMAGE_TARGETS,
    *PYTHON_DEPS,
    *SOURCE_DEPS,
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


def build_linux_pkg(distro, version, cwd, qubes=False):
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
    return CmdAction(" ".join(cmd), cwd=cwd)


def build_deb(cwd):
    """Build a .deb package on Debian Bookworm."""
    return build_linux_pkg(distro="debian", version="bookworm", cwd=cwd)


def build_rpm(version, cwd, qubes=False):
    """Build an .rpm package on the requested Fedora distro."""
    return build_linux_pkg(distro="Fedora", version=version, cwd=cwd, qubes=qubes)


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


def task_download_tessdata():
    """Download the Tesseract data using ./install/common/download-tessdata.py"""
    return {
        "actions": ["python install/common/download-tessdata.py"],
        "file_dep": TESSDATA_DEPS,
        "targets": TESSDATA_TARGETS,
        "clean": True,
    }


def task_build_image():
    """Build the container image using ./install/common/build-image.py"""
    img_src = "share/container.tar.gz"
    img_dst = RELEASE_DIR / f"container-{VERSION}-{ARCH}.tar.gz"  # FIXME: Add arch
    img_id_src = "share/image-id.txt"
    img_id_dst = RELEASE_DIR / "image-id.txt"  # FIXME: Add arch

    return {
        "actions": [
            f"python install/common/build-image.py --runtime={CONTAINER_RUNTIME}",
            ["cp", img_src, img_dst],
            ["cp", img_id_src, img_id_dst],
        ],
        "file_dep": IMAGE_DEPS,
        "targets": [img_src, img_dst, img_id_src, img_id_dst],
        "task_dep": ["init_release_dir", "check_container_runtime"],
        "clean": True,
    }


def task_poetry_install():
    """Setup the Poetry environment"""
    return {"actions": ["poetry install --sync"], "clean": ["poetry env remove --all"]}


def task_macos_build_dmg():
    """Build the macOS .dmg file for Dangerzone."""
    dz_dir = RELEASE_DIR / "tmp" / "macos"
    dmg_src = dz_dir / "dist" / "Dangerzone.dmg"
    dmg_dst = RELEASE_DIR / f"Dangerzone-{VERSION}-{ARCH}.dmg"  # FIXME: Add -arch

    return {
        "actions": [
            (copy_dir, [".", dz_dir]),
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
            "download_tessdata",
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
    """Build a Debian package for Debian Bookworm."""
    dz_dir = RELEASE_DIR / "tmp" / "debian"
    deb_name = f"dangerzone_{VERSION}-1_amd64.deb"
    deb_src = dz_dir / "deb_dist" / deb_name
    deb_dst = RELEASE_DIR / deb_name

    return {
        "actions": [
            (copy_dir, [".", dz_dir]),
            build_deb(cwd=dz_dir),
            ["cp", deb_src, deb_dst],
            ["rm", "-rf", dz_dir],
        ],
        "file_dep": DEB_DEPS,
        "task_dep": ["init_release_dir", "debian_env"],
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
    for version in FEDORA_VERSIONS:
        for qubes in (True, False):
            qubes_ident = "-qubes" if qubes else ""
            qubes_desc = " for Qubes" if qubes else ""
            dz_dir = RELEASE_DIR / "tmp" / f"f{version}{qubes_ident}"
            rpm_names = [
                f"dangerzone{qubes_ident}-{VERSION}-1.fc{version}.x86_64.rpm",
                f"dangerzone{qubes_ident}-{VERSION}-1.fc{version}.src.rpm",
            ]
            rpm_src = [dz_dir / "dist" / rpm_name for rpm_name in rpm_names]
            rpm_dst = [RELEASE_DIR / rpm_name for rpm_name in rpm_names]

            yield {
                "name": version + qubes_ident,
                "doc": f"Build a Fedora {version} package{qubes_desc}",
                "actions": [
                    (copy_dir, [".", dz_dir]),
                    build_rpm(version, cwd=dz_dir, qubes=qubes),
                    ["cp", *rpm_src, RELEASE_DIR],
                    ["rm", "-rf", dz_dir],
                ],
                "file_dep": RPM_DEPS,
                "task_dep": ["init_release_dir", f"fedora_env:{version}"],
                "targets": rpm_dst,
                "clean": True,
            }


def task_git_archive():
    """Build a Git archive of the repo."""
    target = f"{RELEASE_DIR}/dangerzone-{VERSION}.tar.gz"
    return {
        "actions": [
            f"git archive --format=tar.gz -o {target} --prefix=dangerzone/ v{VERSION}"
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

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

from doit import task_params
from doit.action import CmdAction

# if platform.system() in ["Darwin", "Windows"]:
#     CONTAINER_RUNTIME = "docker"
# elif platform.system() == "Linux":
#     CONTAINER_RUNTIME = "podman"
CONTAINER_RUNTIME = "podman"

ARCH = "i686"  # FIXME
VERSION = open("share/version.txt").read().strip()
# FIXME: Make this user-selectable with `get_var()`
RELEASE_DIR = Path.home() / "dz_release_area" / VERSION
FEDORA_VERSIONS = ["39", "40", "41"]
DEBIAN_VERSIONS = ["bullseye", "focal", "jammy", "mantic", "noble", "trixie"]

### Parameters

PARAM_APPLE_ID = {
    "name": "apple_id",
    "long": "apple-id",
    "default": "fpf@example.com",
    "help": "The Apple developer ID that will be used for signing the .dmg",
}


def list_files(path):
    filepaths = []
    for root, _, files in os.walk(path):
        for f in files:
            if f.endswith(".pyc"):
                continue
            filepaths.append(Path(root) / f)
    return filepaths


def copy_dz_dir(src, dst):
    shutil.rmtree(dst)
    dst.mkdir(exist_ok=True)
    shutil.copytree(src, dst)


def cmd_build_linux_pkg(distro, version, cwd, qubes=False):
    pkg = "rpm" if distro == "fedora" else "deb"
    cmd = [
        "python3",
        "./dev_scripts/env.py",
        "--distro",
        distro,
        "--version",
        version,
        "run",
        "--dev"
        f"./dangerzone/install/linux/build-{pkg}.py"
    ]
    if qubes:
        cmd += ["--qubes"]
    return CmdAction(cmd, cwd=cwd)


def task_clean_container_runtime():
    """Clean the storage space of the container runtime."""
    return {
        "actions": None,
        "clean": [
            [CONTAINER_RUNTIME, "system", "prune", "-f"],
        ],
    }


def task_check_python():
    """Check that the latest supported Python version is installed (WIP).

    This task does not work yet, and is currently short-circuited.
    """
    def check_python():
        # FIXME: Check that the latest supported Python release is installed. Use the
        # same logic as we do in dev_scripts/qa.py.
        return True

    return {
        "actions": [check_python],
    }


def task_check_container_runtime():
    """Test that the container runtime is ready."""
    return {
        "actions": [
            ["which", CONTAINER_RUNTIME],
            [CONTAINER_RUNTIME, "ps"],
        ],
    }


def task_check_system():
    """Common status checks for a system."""
    return {
        "actions": None,
        "task_dep": [
            "check_python",
            "check_container_runtime",
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


def task_macos_check_docker_containerd():
    """Test that Docker uses the containard image store."""
    def check_containerd_store():
        cmd = ["docker", "info", "-f", "{{ .DriverStatus }}"]
        driver = subprocess.check_output(cmd, text=True).strip()
        if driver != "[[driver-type io.containerd.snapshotter.v1]]":
            raise RuntimeError(
                f"Probing the Docker image store with {cmd} returned {driver}."
                " Switch to Docker's containerd image store from the Docker Desktop"
                " settings."
            )

    return {
        "actions": [
            "which docker",
            "docker ps",
            check_containerd_store,
        ],
        "params": [PARAM_APPLE_ID],
    }


def task_macos_check_system():
    """Run macOS specific system checks, as well as the generic ones."""
    return {
        "actions": None,
        "task_dep": [
            "check_system",
            "macos_check_cert",
            "macos_check_docker_containerd",
        ],
    }


def task_init_release_dir():
    """Create a directory for release artifacts."""
    def create_release_dir():
        RELEASE_DIR.mkdir(parents=True, exist_ok=True)
        (RELEASE_DIR / "assets").mkdir(exist_ok=True)
        (RELEASE_DIR / "tmp").mkdir(exist_ok=True)

    return {
        "actions": [create_release_dir],
        "targets": [RELEASE_DIR, RELEASE_DIR / "github", RELEASE_DIR / "tmp"],
        "clean": True,
    }


def task_download_tessdata():
    """Download the Tesseract data using ./install/common/download-tessdata.py"""
    tessdata_dir = Path("share") / "tessdata"
    langs = json.loads(open(tessdata_dir.parent / "ocr-languages.json").read()).values()
    targets = [tessdata_dir / f"{lang}.traineddata" for lang in langs]
    targets.append(tessdata_dir)
    return {
        "actions": ["python install/common/download-tessdata.py"],
        "file_dep": [
            "install/common/download-tessdata.py",
            "share/ocr-languages.json",
        ],
        "targets": targets,
        "clean": True,
    }


def task_build_image():
    """Build the container image using ./install/common/build-image.py"""
    return {
        "actions": [
            "python install/common/build-image.py --use-cache=%(use_cache)s",
        ],
        "params": [
            {
                "name": "use_cache",
                "long": "use-cache",
                "help": (
                    "Whether to use cached results or not. For reproducibility reasons,"
                    " it's best to leave it to false"
                ),
                "default": False,
            },
        ],
        "file_dep": [
            "Dockerfile",
            "poetry.lock",
            *list_files("dangerzone/conversion"),
            "dangerzone/gvisor_wrapper/entrypoint.py",
            "install/common/build-image.py",
        ],
        "targets": ["share/container.tar.gz", "share/image-id.txt"],
        "task_dep": ["check_container_runtime"],
        "clean": True,
    }


def task_poetry_install():
    """Setup the Poetry environment"""
    return {
        "actions": ["poetry install --sync"],
    }


def task_macos_build_app():
    """Build the macOS app bundle for Dangerzone."""

    return {
        "actions": [["poetry", "run", "install/macos/build-app.py"]],
        "file_dep": [
            *list_files("share"),
            *list_files("dangerzone"),
            "share/container.tar.gz",
            "share/image-id.txt",
        ],
        "task_dep": ["poetry_install"],
        "targets": ["dist/Dangerzone.app"],
        "clean": ["rm -rf dist/Dangerzone.app"],
    }


def task_macos_codesign():
    return {
        "actions": [
            ["poetry", "run", "install/macos/build-app.py", "--only-codesign"],
            [
                "xcrun notarytool submit --wait --apple-id %(apple_id)s"
                " --keychain-profile dz-notarytool-release-key dist/Dangerzone.dmg",
            ],
        ],
        "params": [PARAM_APPLE_ID],
        "file_dep": ["dist/Dangerzone.app"],
        "targets": ["dist/Dangerzone.dmg"],
        "clean": True,
    }


def task_debian_env():
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
    }


def task_debian_deb():
    dz_dir = RELEASE_DIR / "tmp" / "debian"
    deb_name = f"dangerzone_{VERSION}-1_amd64.deb"
    deb_src = dz_dir / "deb_dist" / deb_name
    deb_dst = RELEASE_DIR / deb_name

    return {
        "actions": [
            (copy_dz_dir, [".", dz_dir]),
            cmd_build_linux_pkg("debian", "bookworm", cwd=dz_dir),
            ["cp", deb_src, deb_dst],
            ["rm", "-r", dz_dir],
        ],
        "file_dep": [
            RELEASE_DIR,
            "share/container.tar.gz",
            "share/image-id.txt",
        ],
        "task_dep": [
            "debian_env",
        ],
        "targets": [deb_dst],
        "clean": True,
    }



def task_fedora_env():
    for version in FEDORA_VERSIONS:
        yield {
            "name": version,
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
        }

def task_fedora_rpm():
    for version in FEDORA_VERSIONS:
        dz_dir = RELEASE_DIR / "tmp" / f"f{version}"
        rpm_names = [
            f"dangerzone-{VERSION}-1.fc{version}.x86_64.rpm",
            f"dangerzone-{VERSION}-1.fc{version}.src.rpm",
            f"dangerzone-qubes-{VERSION}-1.fc{version}.x86_64.rpm",
            f"dangerzone-qubes-{VERSION}-1.fc{version}.src.rpm",
        ]
        rpm_src = [dz_dir / "dist" / rpm_name for rpm_name in rpm_names]
        rpm_dst = [RELEASE_DIR / rpm_name for rpm_name in rpm_names]

        yield {
            "name": version,
            "actions": [
                (copy_dz_dir, [".", dz_dir]),
                cmd_build_linux_pkg("fedora", version, cwd=dz_dir),
                cmd_build_linux_pkg("fedora", version, cwd=dz_dir, qubes=True),
                ["cp", *rpm_src, RELEASE_DIR],
                ["rm", "-r", dz_dir],
            ],
            "file_dep": [
                RELEASE_DIR,
                "share/container.tar.gz",
                "share/image-id.txt",
            ],
            "task_dep": [
                f"fedora_env:{version}",
            ],
            "targets": rpm_dst,
            "clean": True,
        }


@task_params([{
    "name": "apt_tools_prod_dir",
    "default": "~/release/apt-tools-prod"
}])
def task_apt_tools_prod_prep(apt_tools_prod_dir):
    apt_dir = Path(apt_tools_prod_dir).expanduser()
    dz_dir = apt_dir / "dangerzone"

    src = task_debian_deb()["targets"][0]
    deb_name = src.name
    bookworm_deb =  dz_dir / "bookworm" / deb_name
    other_debs = [dz_dir / version / deb_name for version in DEBIAN_VERSIONS]

    def copy_files():
        # Delete previous Dangerzone files.
        old_files = dz_dir.rglob("dangerzone_*j")
        for f in old_files:
            f.unlink()

        # Delete DB entries.
        shutil.rmtree(apt_dir / "db")
        shutil.rmtree(apt_dir / "public" / "dists")
        shutil.rmtree(apt_dir / "public" / "pool")

        # Copy .deb to bookworm folder.
        shutil.copy2(src, bookworm_deb)

        # Create the necessary symlinks
        for deb in other_debs:
            deb.symlink_to(f"../bookworm/{deb_name}")

    return {
        "actions": [copy_files],
        "file_dep": [src],
        "targets": [bookworm_deb, *other_debs],
        "clean": True,
    }

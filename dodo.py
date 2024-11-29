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
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst)


def create_release_dir():
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    (RELEASE_DIR / "assets").mkdir(exist_ok=True)
    (RELEASE_DIR / "tmp").mkdir(exist_ok=True)


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
        "--no-gui",
        "--dev",
        f"./dangerzone/install/linux/build-{pkg}.py"
    ]
    if qubes:
        cmd += ["--qubes"]
    return CmdAction(" ".join(cmd), cwd=cwd)


def task_clean_container_runtime():
    """Clean the storage space of the container runtime."""
    return {
        "actions": None,
        "clean": [
            [CONTAINER_RUNTIME, "system", "prune", "-f"],
        ],
    }


def task_clean_git():
    """Clean the Git repo."""
    return {
        "actions": None,
        "clean": [
            "git clean -fdx",
            "git checkout -f",
        ],
    }


#def task_check_python():
#    """Check that the latest supported Python version is installed (WIP).
#
#    This task does not work yet, and is currently short-circuited.
#    """
#    def check_python_updated():
#        # FIXME: Check that the latest supported Python release is installed. Use the
#        # same logic as we do in dev_scripts/qa.py.
#        return True
#
#    return {
#        "actions": [check_python_updated],
#    }


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
            #"check_python",
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


#def task_macos_check_docker_containerd():
#    """Test that Docker uses the containard image store."""
#    def check_containerd_store():
#        cmd = ["docker", "info", "-f", "{{ .DriverStatus }}"]
#        driver = subprocess.check_output(cmd, text=True).strip()
#        if driver != "[[driver-type io.containerd.snapshotter.v1]]":
#            raise RuntimeError(
#                f"Probing the Docker image store with {cmd} returned {driver}."
#                " Switch to Docker's containerd image store from the Docker Desktop"
#                " settings."
#            )
#
#    return {
#        "actions": [
#            "which docker",
#            "docker ps",
#            check_containerd_store,
#        ],
#        "params": [PARAM_APPLE_ID],
#    }


def task_macos_check_system():
    """Run macOS specific system checks, as well as the generic ones."""
    return {
        "actions": None,
        "task_dep": [
            "check_system",
            "macos_check_cert",
            #"macos_check_docker_containerd",
        ],
    }


def task_init_release_dir():
    """Create a directory for release artifacts."""
    return {
        "actions": [create_release_dir],
        "clean": [f"rm -rf {RELEASE_DIR}"],
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
    img_src = f"share/container-{VERSION}.tar.gz"
    img_dst = RELEASE_DIR / f"container-{VERSION}.tar.gz"  # FIXME: Add arch

    return {
        "actions": [
            "python install/common/build-image.py --use-cache=%(use_cache)s --force-tag=%(force_tag)s",
            f"cp {img_src} {img_dst}",
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
            {
                "name": "force_tag",
                "long": "force-tag",
                "help": (
                    "Build the image using the specified tag. For reproducibility"
                    " reasons, it's best to not use this flag"
                ),
                "default": "",
            },
        ],
        "file_dep": [
            "Dockerfile",
            "poetry.lock",
            *list_files("dangerzone/conversion"),
            "dangerzone/gvisor_wrapper/entrypoint.py",
            "install/common/build-image.py",
        ],
        "targets": [img_src, img_dst],
        "task_dep": [
            "init_release_dir",
            "check_container_runtime",
        ],
        "clean": True,
    }


def task_poetry_install():
    """Setup the Poetry environment"""
    return {
        "actions": ["poetry install --sync"],
    }


def task_macos_build_dmg():
    """Build the macOS app bundle for Dangerzone."""
    dz_dir = RELEASE_DIR / "tmp" / "macos"
    dmg_src = dz_dir / "dist" / "Dangerzone.dmg"
    dmg_dst = RELEASE_DIR / f"Dangerzone-{VERSION}.dmg"  # FIXME: Add -arch

    return {
        "actions": [
            (copy_dz_dir, [".", dz_dir]),
            f"cd {dz_dir} && poetry run install/macos/build-app.py --with-codesign",
            ("xcrun notarytool submit --wait --apple-id %(apple_id)s"
             f" --keychain-profile dz-notarytool-release-key {dmg_src}"),
            f"xcrun stapler staple {dmg_src}",
            ["cp", "-r", dmg_src, dmg_dst],
            ["rm", "-rf", dz_dir],
        ],
        "params": [PARAM_APPLE_ID],
        "file_dep": [
            "poetry.lock",
            "install/macos/build-app.py",
            *list_files("assets"),
            *list_files("share"),
            *list_files("dangerzone"),
            f"share/container-{VERSION}.tar.gz",
        ],
        "task_dep": [
            "init_release_dir",
            "poetry_install"
        ],
        "targets": [dmg_dst],
        "clean": True,
    }


# def task_macos_codesign():
#     dz_dir = RELEASE_DIR / "tmp" / "macos"
#     app_src = RELEASE_DIR / "Dangerzone.app"
#     dmg_src = dz_dir / "dist" / "Dangerzone.dmg"
#     dmg_dst = RELEASE_DIR / "Dangerzone-{VERSION}.dmg"

#     return {
#         "actions": [
#         ],
#         "params": [PARAM_APPLE_ID],
#         "file_dep": [
#             RELEASE_DIR / "Dangerzone.app"
#         ],
#         "targets": ["dist/Dangerzone.dmg"],
#         "clean": True,
#     }


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
        "task_dep": ["check_container_runtime"],
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
            ["rm", "-rf", dz_dir],
        ],
        "file_dep": [
            "poetry.lock",
            "install/linux/build-deb.py",
            *list_files("assets"),
            *list_files("share"),
            *list_files("dangerzone"),
            f"share/container-{VERSION}.tar.gz",
        ],
        "task_dep": [
            "init_release_dir",
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
            "task_dep": ["check_container_runtime"],
        }

def task_fedora_rpm():
    for version in FEDORA_VERSIONS:
        for qubes in (True, False):
            qubes_ident = "-qubes" if qubes else ""
            dz_dir = RELEASE_DIR / "tmp" / f"f{version}{qubes_ident}"
            rpm_names = [
                f"dangerzone{qubes_ident}-{VERSION}-1.fc{version}.x86_64.rpm",
                f"dangerzone{qubes_ident}-{VERSION}-1.fc{version}.src.rpm",
            ]
            rpm_src = [dz_dir / "dist" / rpm_name for rpm_name in rpm_names]
            rpm_dst = [RELEASE_DIR / rpm_name for rpm_name in rpm_names]

            yield {
                "name": version + qubes_ident,
                "actions": [
                    (copy_dz_dir, [".", dz_dir]),
                    #cmd_build_linux_pkg("fedora", version, cwd=dz_dir, qubes=qubes),
                    #["cp", *rpm_src, RELEASE_DIR],
                    ["rm", "-rf", dz_dir],
                ],
                "file_dep": [
                    "poetry.lock",
                    "install/linux/build-rpm.py",
                    *list_files("assets"),
                    *list_files("share"),
                    *list_files("dangerzone"),
                    f"share/container-{VERSION}.tar.gz",
                ],
                "task_dep": [
                    "init_release_dir",
                    f"fedora_env:{version}",
                ],
                "targets": rpm_dst,
                "clean": True,
            }


def copy_files(dz_dir, apt_dir, src, bookworm_deb, other_debs):
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

    return {
        "actions": [(copy_files, [dz_dir, apt_dir, src, bookworm_deb, other_debs])],
        "file_dep": [src],
        "targets": [bookworm_deb, *other_debs],
        "clean": True,
    }

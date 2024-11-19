import os
import platform
import shutil
from pathlib import Path

from doit import task_params
from doit.action import CmdAction

if platform.system() in ["Darwin", "Windows"]:
    CONTAINER_RUNTIME = "docker"
elif platform.system() == "Linux":
    CONTAINER_RUNTIME = "podman"

VERSION = open("share/version.txt").read().strip()
RELEASE_DIR = Path.home() / "release" / VERSION
FEDORA_VERSIONS = ["39", "40", "41"]
DEBIAN_VERSIONS = ["bullseye", "focal", "jammy", "mantic", "noble", "trixie"]


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


def task_check_python():
    def check_python():
        # FIXME: Check that Python 3.12 is installed.
        return True

    return {
        "actions": [check_python],
    }


def task_container_runtime():
    return {
        "actions": [
            ["which", CONTAINER_RUNTIME],
            [CONTAINER_RUNTIME, "ps"],
        ],
    }


def task_system_checks():
    return {
        "actions": None,
        "task_dep": [
            "check_python",
            "container_runtime",
        ],
    }


def task_download_tessdata():
    return {
        "actions": [["python", "install/common/download-tessdata.py"]],
        "file_dep": [
            "install/common/download-tessdata.py",
            "share/ocr-languages.json",
        ],
        "targets": ["share/tessdata"]
    }


def task_build_container():
    return {
        "actions": ["python install/common/build-image.py --use-cache=%(use_cache)s"],
        "params": [
            {
                "name": "use_cache",
                "long": "use-cache",
                "default": False,
            }
        ],
        "file_dep": [
            "Dockerfile",
            "poetry.lock",
            *list_files("dangerzone/conversion"),
            "dangerzone/gvisor_wrapper/entrypoint.py",
        ],
        "targets": ["share/container.tar.gz", "share/image-id.txt"],
        "task_dep": ["container_runtime"],
    }


def task_poetry_install():
    return {
        "actions": ["poetry install --sync"],
    }


def task_app():
    return {
        "actions": [["poetry", "run", "install/macos/build-app.py"]],
        "file_dep": [
            *list_files("share"),
            *list_files("dangerzone"),
        ],
        "task_dep": ["poetry_install"],
        "targets": ["dist/Dangerzone.app"]
    }


def task_codesign():
    return {
        "actions": [
            ["poetry", "run", "install/macos/build-app.py"],
            [
                "xcrun",
                "notarytool",
                "submit",
                "--wait",
                "--apple-id",
                "<email>",
                "--keychain-profile",
                "dz-notarytool-release-key",
                "dist/Dangerzone.dmg",
            ],
        ],
        "file_dep": ["dist/Dangerzone.app"],
        "targets": ["dist/Dangerzone.dmg"]
    }


def task_init_release_dir():
    def create_release_dir():
        RELEASE_DIR.mkdir(parents=True, exist_ok=True)
        (RELEASE_DIR / "github").mkdir(exist_ok=True)
        (RELEASE_DIR / "tmp").mkdir(exist_ok=True)

    return {
        "actions": [create_release_dir],
        "targets": [RELEASE_DIR, RELEASE_DIR / "github", RELEASE_DIR / "tmp"],
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
        "targets": [deb_dst]
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
            "targets": rpm_dst
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
        "targets": [bookworm_deb, *other_debs]
    }

import functools
import logging
import platform
import subprocess
from typing import Optional

from . import errors
from .util import subprocess_run

log = logging.getLogger(__name__)


def wsl_list() -> str:
    """List WSL distributions."""
    return subprocess_run(
        ["wsl", "-l", "--quiet"],
        check=True,
        capture_output=True,
        # encoding="UTF-16LE",
    ).stdout


def wsl_status() -> str:
    """Get status of WSL engine."""
    return subprocess_run(
        ["wsl", "--status"],
        check=True,
        capture_output=True,
        # encoding="UTF-16LE",
    ).stdout


def wsl_install(no_distribution: bool = True) -> None:
    """Install WSL, optionally without a default distribution."""
    cmd = ["wsl", "--install"]
    if no_distribution:
        cmd.append("--no-distribution")
    # subprocess_run(cmd, check=True, encoding="UTF-16LE")
    subprocess_run(cmd, check=True)


def wsl_update() -> None:
    """Install WSL, optionally without a default distribution."""
    # subprocess_run(cmd, check=True, encoding="UTF-16LE")
    subprocess_run(["wsl", "--update"], check=True)


def is_wsl_installed() -> bool:
    """Return whether WSL is installed or not."""
    try:
        wsl_status()
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise errors.WSLNotInstalled


def install_wsl_and_check_reboot() -> None:
    """Install WSL and check if a reboot is required."""
    if is_wsl_installed():
        return

    # NOTE: We choose the following methods, due to the devices we have tested WSL on.
    # 1. On a Windows 11 machine, any of these three methods should work.
    # 2. On a recently updated Windows 10 machine, 'wsl --install [--no-distribution]'
    #    reportedly works.
    # 3. On the windows-2022 GitHub runner, it seems that only 'wsl --update' works.
    methods = [
        (wsl_update, "wsl --update"),
        (
            functools.partial(wsl_install, no_distribution=True),
            "wsl --install --no-distribution",
        ),
        (wsl_install, "wsl --install"),
    ]

    for func, cmd in methods:
        log.info(f"Attempting to install WSL via '{cmd}'")
        try:
            func()
            if not is_wsl_installed():
                raise errors.WSLInstallNeedsReboot
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            pass

    raise errors.WSLInstallFailed

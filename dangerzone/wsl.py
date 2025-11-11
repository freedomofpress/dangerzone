import functools
import logging
import platform
import subprocess
from typing import Callable, Optional, Tuple

from . import errors
from .util import subprocess_run

log = logging.getLogger(__name__)


def wsl_list() -> str:
    """List WSL distributions."""
    return subprocess_run(
        ["wsl", "-l", "--quiet"],
        check=True,
        capture_output=True,
        # errors="replace",
        encoding="UTF-16LE",
    ).stdout


def wsl_status() -> str:
    """Get status of WSL engine."""
    return subprocess_run(
        ["wsl", "--status"],
        check=True,
        capture_output=True,
        encoding="UTF-16LE",
        # errors="replace",
    ).stdout


def wsl_install(no_distribution: bool = True) -> None:
    """Install WSL, optionally without a default distribution."""
    cmd = ["wsl", "--install"]
    if no_distribution:
        cmd.append("--no-distribution")
    return subprocess_run(cmd, check=True, encoding="UTF-16LE")
    # subprocess.run(cmd, check=True, errors="replace")


def wsl_update() -> None:
    """Install WSL, optionally without a default distribution."""
    return subprocess_run(["wsl", "--update"], check=True, encoding="UTF-16LE")
    # subprocess_run(["wsl", "--update"], check=True, errors="replace")


def is_wsl_installed() -> bool:
    """Return whether WSL is installed or not."""
    try:
        wsl_status()
        return True
    except subprocess.CalledProcessError as e:
        return False


def install_wsl_and_check_reboot() -> None:
    """Install WSL and check if a reboot is required."""
    if is_wsl_installed():
        return

    # NOTE: We choose the following methods, due to the devices we have tested WSL on.
    # 1. On a Windows 11 machine, any of these three methods should work.
    # 2. On a recently updated Windows 10 machine, 'wsl --install [--no-distribution]'
    #    reportedly works.
    # 3. On the windows-2022 GitHub runner, it seems that only 'wsl --update' works.
    methods: list[Tuple[Callable, str]] = [
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
            if is_wsl_installed():
                return
            else:
                raise errors.WSLInstallNeedsReboot
        except subprocess.CalledProcessError as e:
            log.info(f"Did not manage to install WSL via '{cmd}'")

    raise errors.WSLInstallFailed

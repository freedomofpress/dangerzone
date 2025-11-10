import logging
import platform
import subprocess
from typing import Optional

from . import errors
from .util import subprocess_run

log = logging.getLogger(__name__)


def wsl_list() -> None:
    """Check if WSL is installed by running 'wsl -l --quiet'."""
    try:
        subprocess_run(
            ["wsl", "-l", "--quiet"],
            check=True,
            capture_output=True,
            encoding="UTF16LE",
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise Exception("WSL is not installed") from e


def wsl_install(no_distribution: bool = True) -> None:
    """Install WSL, optionally without a default distribution."""
    cmd = ["wsl", "--install"]
    if no_distribution:
        cmd.append("--no-distribution")
    try:
        subprocess_run(cmd, check=True, encoding="UTF16LE")
    except subprocess.CalledProcessError as e:
        raise errors.WSLInstallFailed("Failed to install WSL") from e


def is_wsl_installed() -> bool:
    """Return whether WSL is installed or not."""
    try:
        wsl_list()
        return True
    except Exception:
        return False


def install_wsl_and_check_reboot() -> None:
    """Install WSL and check if a reboot is required."""
    if is_wsl_installed():
        return

    log.info("Attempting to install WSL with --no-distribution")
    try:
        wsl_install(no_distribution=True)
        raise errors.WSLInstallNeedsReboot()
    except errors.WSLInstallFailed as e1:
        log.warning(
            "Failed to install WSL with --no-distribution, trying without it..."
        )
        try:
            wsl_install(no_distribution=False)
            raise errors.WSLInstallNeedsReboot()
        except errors.WSLInstallFailed as e2:
            raise errors.WSLInstallFailed(
                "Failed to install WSL, both with and without --no-distribution"
            ) from e2

import functools
import logging
import platform
import subprocess
from typing import Callable, Optional, Tuple

from .. import errors
from ..util import subprocess_run
from . import shellexec

log = logging.getLogger(__name__)


def status() -> str:
    """Get status of WSL engine."""
    # In this command, we set the encoding to non-BOM UTF16, which is what WSL
    # uses. If not set, stdout will contain invisible null characters which renders the
    # output impossible to read and copy/paste.
    #
    # Note that this is not necessary for commands initiated with ShellExecuteEx, since
    # they don't print to a handle that Python controls, but to a terminal spawned by
    # Windows.
    return subprocess_run(
        ["wsl", "--status"],
        check=True,
        capture_output=True,
        encoding="UTF-16LE",
    ).stdout


def install(no_distribution: bool = True) -> None:
    """Install WSL, optionally without a default distribution."""
    cmd = ["wsl", "--install"]
    if no_distribution:
        cmd.append("--no-distribution")

    # NOTE: On Windows 11, running `wsl --install` somehow does not work with
    # subprocess.run. It works via `ShellExecuteEx` though, which is what we use here.
    shellexec.run(cmd, check=True)


def update() -> None:
    """Update WSL kernel."""
    # NOTE: On Windows 11, running `wsl --update` somehow does not work with
    # subprocess.run. It works via `ShellExecuteEx` though, which is what we use here.
    shellexec.run(["wsl", "--update"], check=True)


def is_installed() -> bool:
    """Return whether WSL is installed or not."""
    try:
        status()
        return True
    except subprocess.CalledProcessError as e:
        return False


def install_and_check_reboot() -> None:
    """Install WSL and check if a reboot is required."""
    # Context: https://github.com/freedomofpress/dangerzone/issues/1312

    if is_installed():
        return

    # NOTE: We choose the following methods, due to the devices we have tested WSL on.
    # 1. On a Windows 11 machine, any of these three methods should work.
    # 2. On a recently updated Windows 10 machine, 'wsl --install [--no-distribution]'
    #    reportedly works, but not `wsl --update`.
    # 3. On the windows-2022 GitHub runner, which is based on Windows 10, it seems that
    #    only `wsl --update` works, in the sense that it updates the outdated WSL kernel
    #    that it has.
    methods: list[Tuple[Callable, str]] = [
        (update, "wsl --update"),
        (
            functools.partial(install, no_distribution=True),
            "wsl --install --no-distribution",
        ),
        (install, "wsl --install"),
    ]

    for func, cmd in methods:
        log.info(f"Attempting to install WSL via '{cmd}'")
        try:
            func()
            # FIXME: At this point, we know that the WSL installation has succeeded. We
            # don't know though if a reboot is required. To be fair, I don't think that
            # Windows knows that either. If we run `wsl --status`, it may or may not
            # report an error. If we run:
            #
            #     dism.exe /online /get-featureinfo /featurename:...
            #
            # it reports that you "possibly" need a reboot.
            #
            # I suggest we err on the side of rebooting here, even though Podman can
            # detect if the computer needs a reboot or not.
            raise errors.WSLInstallNeedsReboot(
                "Windows Subsystem for Linux (WSL) was installed, but you need to"
                " reboot your computer before Dangerzone can use it."
            )
        except errors.WinShellExecError as e:
            log.info(f"Did not manage to install WSL via '{cmd}': {e}")

    raise errors.WSLInstallFailed(
        "Dangerzone failed to install the Windows Subsystem for Linux (WSL),"
        " which is required for it to work. You can attempt to install it on"
        " your own with 'wsl --install', or check some troubleshooting tips:"
        " https://podman-desktop.io/docs/troubleshooting/troubleshooting-podman-on-windows"
    )

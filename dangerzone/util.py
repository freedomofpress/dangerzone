import pathlib
import platform
import string
import subprocess
import sys
import time
from typing import Optional, Self

import appdirs


def get_config_dir() -> str:
    return appdirs.user_config_dir("dangerzone")


def get_tmp_dir() -> Optional[str]:
    """Get the parent dir for the Dangerzone temporary dirs.

    This function returns the parent directory where Dangerzone will store its temporary
    directories. The default behavior is to let Python choose for us (e.g., in `/tmp`
    for Linux), which is why we return None. However, we still need to define this
    function in order to be able to set this dir via mocking in our tests.
    """
    return None


def get_resource_path(filename: str) -> str:
    if getattr(sys, "dangerzone_dev", False):
        # Look for resources directory relative to python file
        project_root = pathlib.Path(__file__).parent.parent
        prefix = project_root.joinpath("share")
    else:
        if platform.system() == "Darwin":
            bin_path = pathlib.Path(sys.executable)
            app_path = bin_path.parent.parent
            prefix = app_path.joinpath("Resources", "share")
        elif platform.system() == "Linux":
            prefix = pathlib.Path(sys.prefix).joinpath("share", "dangerzone")
        elif platform.system() == "Windows":
            exe_path = pathlib.Path(sys.executable)
            dz_install_path = exe_path.parent
            prefix = dz_install_path.joinpath("share")
        else:
            raise NotImplementedError(f"Unsupported system {platform.system()}")
    resource_path = prefix.joinpath(filename)
    return str(resource_path)


def get_version() -> str:
    try:
        with open(get_resource_path("version.txt")) as f:
            version = f.read().strip()
    except FileNotFoundError:
        # In dev mode, in Windows, get_resource_path doesn't work properly for the container, but luckily
        # it doesn't need to know the version
        version = "unknown"
    return version


def get_subprocess_startupinfo():  # type: ignore [no-untyped-def]
    if platform.system() == "Windows":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return startupinfo
    else:
        return None


def replace_control_chars(untrusted_str: str) -> str:
    """Remove control characters from string. Protects a terminal emulator
    from obcure control characters"""
    sanitized_str = ""
    for char in untrusted_str:
        sanitized_str += char if char in string.printable else "_"
    return sanitized_str


class Stopwatch:
    """A simple stopwatch implementation.

    This class offers a very simple stopwatch implementation, with the following
    interface:

    * self.start(): Start the stopwatch.
    * self.stop(): Stop the stopwatch.
    * self.elapsed: Measure the time from now since when the stopwatch started. If the
      stopwatch has stopped, measure the time until stopped.
    * self.remaining: If the user has provided a timeout, measure the time remaining
      until the timeout expires. Will raise a TimeoutError if the timeout has been
      surpassed.

    This class can also be used as a context manager.
    """

    def __init__(self, timeout: Optional[float] = None) -> None:
        self.timeout = timeout
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    @property
    def elapsed(self) -> float:
        """Check how much time has passed since the start of the stopwatch."""
        if self.start_time is None:
            raise RuntimeError("The stopwatch has not started yet")
        return (self.end_time or time.monotonic()) - self.start_time

    @property
    def remaining(self) -> float:
        """Check how much time remains until the timeout expires (if provided)."""
        if self.timeout is None:
            raise RuntimeError("Cannot calculate remaining time without timeout")

        remaining = self.timeout - self.elapsed

        if remaining < 0:
            raise TimeoutError(
                "Timeout ({timeout}s) has been surpassed by {-remaining}s"
            )

        return remaining

    def __enter__(self) -> "Stopwatch":
        self.start_time = time.monotonic()
        return self

    def start(self) -> None:
        self.__enter__()

    def __exit__(self, *args: list) -> None:
        self.end_time = time.monotonic()

    def stop(self) -> None:
        self.__exit__()

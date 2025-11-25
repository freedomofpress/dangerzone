import functools
import os
import platform
import subprocess
import sys
import traceback
import unicodedata
from pathlib import Path
from typing import Any

try:
    import platformdirs
except ImportError:
    import appdirs as platformdirs  # type: ignore[no-redef]


# FIXME: We are using `subprocess.STARTF_USESHOWWINDOW` here, but there's a more
# modern way since Python 3.7 (see also https://github.com/python/cpython/issues/85785)
@functools.wraps(subprocess.run)
def subprocess_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess:
    if platform.system() == "Windows":
        startupinfo = subprocess.STARTUPINFO()  # type: ignore [attr-defined]
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore [attr-defined]
        kwargs.setdefault("startupinfo", startupinfo)
    return subprocess.run(*args, **kwargs)


def get_architecture() -> str:
    """Return the currently detected architecture (amd64 or arm64)"""
    machine = platform.machine().lower()
    # Normalize architecture names
    return {"x86_64": "amd64", "amd64": "amd64", "arm64": "arm64"}.get(machine, machine)


def get_cache_dir() -> Path:
    return Path(platformdirs.user_cache_dir("dangerzone"))


def get_config_dir() -> Path:
    return Path(platformdirs.user_config_dir("dangerzone"))


def get_resource_path(filename: str) -> Path:
    if getattr(sys, "dangerzone_dev", False):
        # Look for resources directory relative to python file
        project_root = Path(__file__).parent.parent
        prefix = project_root / "share"
    else:
        if platform.system() == "Darwin":
            bin_path = Path(sys.executable)
            app_path = bin_path.parent.parent
            prefix = app_path / "Resources" / "share"
        elif platform.system() == "Linux":
            prefix = Path(sys.prefix) / "share" / "dangerzone"
        elif platform.system() == "Windows":
            exe_path = Path(sys.executable)
            dz_install_path = exe_path.parent
            prefix = dz_install_path / "share"
        else:
            raise NotImplementedError(f"Unsupported system {platform.system()}")
    return prefix / filename


def get_tessdata_dir() -> Path:
    if getattr(sys, "dangerzone_dev", False) or platform.system() in (
        "Windows",
        "Darwin",
    ):
        # Always use the tessdata path from the Dangerzone ./share directory, for
        # development builds, or in Windows/macOS platforms.
        return get_resource_path("tessdata")

    # In case of Linux systems, grab the Tesseract data from any of the following
    # locations. We have found some of the locations through trial and error, whereas
    # others are taken from the docs:
    #
    #     [...] Possibilities are /usr/share/tesseract-ocr/tessdata or
    #     /usr/share/tessdata or /usr/share/tesseract-ocr/4.00/tessdata. [1]
    #
    # [1] https://tesseract-ocr.github.io/tessdoc/Installation.html
    tessdata_dirs = [
        Path("/usr/share/tessdata/"),  # on some Debian
        Path("/usr/share/tesseract/tessdata/"),  # on Fedora
        Path("/usr/share/tesseract-ocr/tessdata/"),  # ? (documented)
        Path("/usr/share/tesseract-ocr/4.00/tessdata/"),  # on Debian Bullseye
        Path("/usr/share/tesseract-ocr/5/tessdata/"),  # on Debian Trixie
    ]

    for dir in tessdata_dirs:
        if dir.is_dir():
            return dir

    raise RuntimeError("Tesseract language data are not installed in the system")


def get_version() -> str:
    """Returns the Dangerzone version string."""
    try:
        with get_resource_path("version.txt").open() as f:
            version = f.read().strip()
    except FileNotFoundError:
        # In dev mode, in Windows, get_resource_path doesn't work properly for the container, but luckily
        # it doesn't need to know the version
        version = "unknown"
    return version


def replace_control_chars(untrusted_str: str, keep_newlines: bool = False) -> str:
    """Remove control characters from string. Protects a terminal emulator
    from obscure control characters.

    Control characters are replaced by � U+FFFD Replacement Character.

    If a user wants to keep the newline character (e.g., because they are sanitizing a
    multi-line text), they must pass `keep_newlines=True`.
    """

    def is_safe(chr: str) -> bool:
        """Return whether Unicode character is safe to print in a terminal
        emulator, based on its General Category.

        The following General Category values are considered unsafe:

        * C* - all control character categories (Cc, Cf, Cs, Co, Cn)
        * Zl - U+2028 LINE SEPARATOR only
        * Zp - U+2029 PARAGRAPH SEPARATOR only
        """
        categ = unicodedata.category(chr)
        if categ.startswith("C") or categ in ("Zl", "Zp"):
            return False
        return True

    sanitized_str = ""
    for char in untrusted_str:
        if (keep_newlines and char == "\n") or is_safe(char):
            sanitized_str += char
        else:
            sanitized_str += "�"
    return sanitized_str


def format_exception(e: Exception) -> str:
    # The signature of traceback.format_exception has changed in python 3.10
    if sys.version_info < (3, 10):
        output = traceback.format_exception(*sys.exc_info())
    else:
        output = traceback.format_exception(e)

    return "".join(output)


@functools.cache
def linux_system_is(*names: str) -> bool:
    """Checks if any of the given names are present in /etc/os-release (on Linux)"""
    if platform.system() == "Linux":
        os_release_path = Path("/etc/os-release")
        if os_release_path.exists():
            os_release = os_release_path.read_text()
            return any([name in os_release for name in names])
    return False


def get_tails_socks_proxy() -> str:
    """
    Generate a SOCKS5 proxy connection address that works on Tails.

    Passing a random value for username makes C Tor use stream isolation,
    which allows to isolate unrelated streams, putting them on separate
    circuits so that semantically unrelated traffic is not inadvertently
    made linkable [1].

    This authentication scheme is to be upgraded to "<torS0X>" [0] when
    Tor hits 0.4.9.1 in Tails (currently 0.4.8.19) or if Tails switches
    to Arti (1.2.8+)

    [0] https://spec.torproject.org/socks-extensions.html#extended-auth
    [1] https://spec.torproject.org/proposals/171-separate-streams.txt
    """
    return f"socks5://{os.urandom(8).hex()}:0@127.0.0.1:9050"

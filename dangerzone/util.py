import os
import pathlib
import platform
import subprocess
import sys
import unicodedata
from typing import Optional

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
        prefix = project_root / "share"
    else:
        if platform.system() == "Darwin":
            bin_path = pathlib.Path(sys.executable)
            app_path = bin_path.parent.parent
            prefix = app_path / "Resources" / "share"
        elif platform.system() == "Linux":
            prefix = pathlib.Path(sys.prefix) / "share" / "dangerzone"
        elif platform.system() == "Windows":
            exe_path = pathlib.Path(sys.executable)
            dz_install_path = exe_path.parent
            prefix = dz_install_path / "share"
        else:
            raise NotImplementedError(f"Unsupported system {platform.system()}")
    resource_path = prefix / filename
    return str(resource_path)


def get_tessdata_dir() -> str:
    if (
        getattr(sys, "dangerzone_dev", False)
        or platform.system() == "Windows"
        or platform.system() == "Darwin"
    ):
        # Always use the tessdata path from the Dangerzone ./share directory, for
        # development builds, or in Windows/macOS platforms.
        return get_resource_path("tessdata")

    fedora_tessdata_dir = "/usr/share/tesseract/tessdata/"
    debian_tessdata_dir = "/usr/share/tessdata/"
    if os.path.isdir(fedora_tessdata_dir):
        return fedora_tessdata_dir
    if os.path.isdir(debian_tessdata_dir):
        return debian_tessdata_dir
    else:
        raise RuntimeError("Tesseract language data are not installed in the system")


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

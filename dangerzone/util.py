import pathlib
import platform
import subprocess
import sys
import unicodedata

import appdirs


def get_config_dir() -> str:
    return appdirs.user_config_dir("dangerzone")


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


def get_tessdata_dir() -> pathlib.Path:
    if getattr(sys, "dangerzone_dev", False) or platform.system() in (
        "Windows",
        "Darwin",
    ):
        # Always use the tessdata path from the Dangerzone ./share directory, for
        # development builds, or in Windows/macOS platforms.
        return pathlib.Path(get_resource_path("tessdata"))

    # In case of Linux systems, grab the Tesseract data from any of the following
    # locations. We have found some of the locations through trial and error, whereas
    # others are taken from the docs:
    #
    #     [...] Possibilities are /usr/share/tesseract-ocr/tessdata or
    #     /usr/share/tessdata or /usr/share/tesseract-ocr/4.00/tessdata. [1]
    #
    # [1] https://tesseract-ocr.github.io/tessdoc/Installation.html
    tessdata_dirs = [
        pathlib.Path("/usr/share/tessdata/"),  # on Debian
        pathlib.Path("/usr/share/tesseract/tessdata/"),  # on Fedora
        pathlib.Path(
            "/usr/share/tesseract-ocr/tessdata/"
        ),  # ? (documented, but not encountered)
        pathlib.Path("/usr/share/tesseract-ocr/4.00/tessdata/"),  # on Ubuntu
    ]

    for dir in tessdata_dirs:
        if dir.is_dir():
            return dir

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

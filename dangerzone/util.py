import platform
import subprocess
import sys
import traceback
import unicodedata
from pathlib import Path

try:
    import platformdirs
except ImportError:
    import appdirs as platformdirs  # type: ignore[no-redef]


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


def format_exception(e: Exception) -> str:
    # The signature of traceback.format_exception has changed in python 3.10
    if sys.version_info < (3, 10):
        output = traceback.format_exception(*sys.exc_info())
    else:
        output = traceback.format_exception(e)

    return "".join(output)

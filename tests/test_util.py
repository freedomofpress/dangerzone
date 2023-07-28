import platform
import subprocess
from pathlib import Path

import pytest

from dangerzone import util

from . import sanitized_text, uncommon_text

VERSION_FILE_NAME = "version.txt"


def test_get_resource_path() -> None:
    share_dir = Path("share").resolve()
    resource_path = Path(util.get_resource_path(VERSION_FILE_NAME)).parent
    assert share_dir.samefile(
        resource_path
    ), f"{share_dir} is not the same file as {resource_path}"


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific")
def test_get_subprocess_startupinfo() -> None:
    startupinfo = util.get_subprocess_startupinfo()
    assert isinstance(startupinfo, subprocess.STARTUPINFO)  # type: ignore[attr-defined]


def test_replace_control_chars(uncommon_text: str, sanitized_text: str) -> None:
    """Test that the replace_control_chars() function works properly."""
    assert util.replace_control_chars(uncommon_text) == sanitized_text
    assert util.replace_control_chars("normal text") == "normal text"
    assert util.replace_control_chars("") == ""

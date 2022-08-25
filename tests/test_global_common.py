import os
import platform
from pathlib import Path

import pytest
from strip_ansi import strip_ansi  # type: ignore

import dangerzone.global_common

VERSION_FILE_NAME = "version.txt"


@pytest.fixture
def global_common():
    return dangerzone.global_common.GlobalCommon()


class TestGlobalCommon:
    def test_get_resource_path(self, global_common):
        share_dir = Path("share").resolve()
        resource_path = Path(global_common.get_resource_path(VERSION_FILE_NAME)).parent
        assert share_dir.samefile(
            resource_path
        ), f"{share_dir} is not the same file as {resource_path}"

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific")
    def test_get_subprocess_startupinfo(self, global_common):
        startupinfo = global_common.get_subprocess_startupinfo()
        self.assertIsInstance(startupinfo, subprocess.STARTUPINFO)

    def test_display_banner(self, global_common, capfd):
        global_common.display_banner()  # call the test subject
        (out, err) = capfd.readouterr()
        plain_lines = [strip_ansi(line) for line in out.splitlines()]
        assert "╭──────────────────────────╮" in plain_lines, "missing top border"
        assert "╰──────────────────────────╯" in plain_lines, "missing bottom border"

        banner_width = len(plain_lines[0])
        for line in plain_lines:
            assert len(line) == banner_width, "banner has inconsistent width"

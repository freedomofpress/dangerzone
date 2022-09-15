import os
import platform
from pathlib import Path

import pytest

import dangerzone.global_common


@pytest.fixture
def global_common():
    return dangerzone.global_common.GlobalCommon()


class TestGlobalCommon:
    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific")
    def test_get_subprocess_startupinfo(self, global_common):
        startupinfo = global_common.get_subprocess_startupinfo()
        self.assertIsInstance(startupinfo, subprocess.STARTUPINFO)

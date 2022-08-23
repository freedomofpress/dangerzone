import io
import os
import platform
import subprocess
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest import TestCase, mock

from strip_ansi import strip_ansi  # type: ignore

import dangerzone.global_common as global_common


class TestGlobalCommon(TestCase):

    VERSION_FILE_NAME = "version.txt"

    def setUp(self):
        self.global_common = global_common.GlobalCommon()
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        sys.dangerzone_dev = True

    def test_get_resource_path(self):
        share_dir = Path("share").resolve()
        resource_path = Path(
            self.global_common.get_resource_path(self.VERSION_FILE_NAME)
        ).parent
        self.assertTrue(
            share_dir.samefile(resource_path),
            msg=f"{share_dir} is not the same file as {resource_path}",
        )

    @unittest.skipUnless(platform.system() == "Windows", "STARTUPINFO is for Windows")
    def test_get_subprocess_startupinfo(self):
        startupinfo = self.global_common.get_subprocess_startupinfo()
        self.assertIsInstance(startupinfo, subprocess.STARTUPINFO)

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_display_banner(self, mock_stdout: StringIO):
        self.global_common.display_banner()  # call the test subject
        banner = mock_stdout.getvalue()
        plain_lines = [strip_ansi(line) for line in banner.splitlines()]
        with self.subTest("banner top border"):
            self.assertEqual("╭──────────────────────────╮", plain_lines[0])
        with self.subTest("banner bottom border"):
            self.assertEqual("╰──────────────────────────╯", plain_lines[14])
        with self.subTest("banner consistent dimensions"):
            width = len(plain_lines[0])
            for line in plain_lines:
                self.assertEqual(len(line), width)

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_display_banner_dims(self, mock_stdout: StringIO):
        self.global_common.display_banner()  # call the test subject
        banner = mock_stdout.getvalue()
        banner_lines = banner.splitlines()
